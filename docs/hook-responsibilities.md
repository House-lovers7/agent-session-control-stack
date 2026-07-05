# Hook 責務分離と競合回避（Claude Code binding）

> Phase 0 設計原本。3 ツールの hook / proxy 面を重ねたときの実挙動と、競合を構成で解消するルール。

## 1. 責務マトリクス（検証済み事実ベース）

| 面 | session-health v0.3.1 | compact-plus | pxpipe |
|---|---|---|---|
| **UserPromptSubmit** | hot 時のみ additionalContext 注入（約 60 トークン、`REWARN_EVERY`=20 リクエストごと最大 1 回）。内容: /compact・新セッション提案 + subagent 委譲指示 | ①recovery 注入: PostCompact が書いた marker を消費し、state file / active plan 参照 +「原ファイルが authoritative」注記を注入（compact 直後の 1 回のみ）。②reminder: warn marker を消費し /compact 推奨 + 3 行 state recitation を注入 | — |
| **PreCompact** | 登録なし | transcript backup（→ `~/.claude/backups/transcripts/`、timeout 30s）+ 10 セクション state file 生成（LLM バックエンド、timeout 180s） | — |
| **PostCompact** | 登録なし（transcript の `compact_boundary` レコードを scan 時に検出して live segment カウンタをリセット） | recovery marker 書き込み + warn cooldown リセット | — |
| **statusline / Stop** | オプトイン（ユーザーが自分の statusline / Stop hook に 1 行足す方式。plugin は自動登録しない） | —（warn marker の生成は作者の外部 statusline.sh の責務） | — |
| **リクエスト経路（proxy）** | — | — | `/v1/messages` POST をインターセプトし、対象コンテンツを PNG 化して上流へ転送 |

## 2. 競合分析

### 2.1 競合するのは UserPromptSubmit だけ

- PreCompact / PostCompact は compact-plus の専有。session-health は compact 認識を hook ではなく transcript レコード読取りで行うため、イベント面で衝突しない
- pxpipe は hook ですらない（プロキシ）。hook の出力（additionalContext）はリクエスト本文に入るため pxpipe の変換対象になり得るが、どちらの注入も小さく（60 トークン級）、pxpipe の画像化閾値（数千文字）に届かない → 実害なし [中: 閾値仕様からの推定]

### 2.2 UserPromptSubmit 上の共存条件

同一イベントに複数 plugin の hook が並ぶこと自体は問題ない。共存条件は:

1. **注入が小さい** — session-health ~60 トークン、compact-plus recovery も参照+注記のみ。両方同時に発火しても数百トークン以内
2. **発火条件が排他的に近い** — session-health は「hot が続いているとき」、compact-plus recovery は「compact 直後の 1 回」。compact 直後は session-health の live segment がリセットされるため hot 判定も解除される。同時発火はほぼ起きない [高: 双方のリセットロジックを確認済み]
3. **fail open** — 双方とも失敗時は silent exit で、プロンプト送信をブロックしない

### 2.3 唯一の実質的競合: 「/compact を勧める声」の二重化

- session-health: hot 判定 → モデルに /compact・新セッションを提案させる
- compact-plus reminder: context 使用率 ≥60% → /compact 推奨を直接注入

両方生きていると、判定基準の異なる 2 つの「畳め」がモデルに届く。

## 3. 競合回避ルール（本 stack の規約）

```
Rule 1: compact 提案の意思決定者は session-health のみ。
Rule 2: compact-plus の reminder は導入しない（構成的 off）。
Rule 3: pxpipe は判断に関与しない。圧縮の on/off はモデル allowlist で制御する。
```

### Rule 2 の実装方法（設定ではなく構成）

compact-plus の reminder は「外部 statusline が `${TMPDIR}/claude-compact-warn/...` に warn marker を書く → plugin が消費する」疎結合設計。**marker 生成側（作者の base repo の statusline.sh 相当）を導入しなければ、reminder hook は `[[ -f "$WARN_MARKER" ]] || exit 0` で即終了し、一度も発火しない。** state capture / backup / recovery は marker と無関係に動く。

- フォーク不要、hooks.json の編集不要、無効化 env も不要
- 逆に、reminder を使いたい場合のみ marker 生成器を自作 statusline に足す（本 stack では非推奨）

### 注入トークン予算

UserPromptSubmit 由来の注入合計は通常時 0、hot 時 ~60 トークン、compact 直後 ~数百トークン以内に収まる。これを超える注入を足す場合（他 plugin 追加時）は本マトリクスを更新すること。

## 4. 併用時の env 規約（examples/claude-code/settings.example.json に反映）

| env | 推奨値 | 理由 |
|---|---|---|
| `SESSION_HEALTH_*` | 既定のまま | 実測に基づく既定値。チューニングは測定後 |
| `COMPACT_PLUS_PRIMARY_BACKEND` | `""`（スキップ）を初期値 | 既定 `claude -p` は課金 API。有効化は明示オプトイン |
| `COMPACT_PLUS_FALLBACK_BACKEND` | `""` | 同上（`codex exec` も課金） |
| `PXPIPE_MODELS` | 既定（`claude-fable-5,gpt-5.6`） | Opus 系は誤読率が高く既定で対象外。広げない |
| `CLAUDE_CODE_SUBAGENT_MODEL` | byte-exact 作業時に allowlist 外モデルを指定 | 圧縮経路から逃がす唯一の選択的制御 |

注: `COMPACT_PLUS_PRIMARY_BACKEND=""` にすると 10 セクション state file は生成されない（transcript backup と recovery marker は動く）。state file まで使う場合は課金を承知で有効化するか、Codex binding と同様の手動 checkpoint（templates/state-file.md）を使う。
