# Opus 5 への既定モデル切替 — 仕様・リポジトリ影響・ローカル実測

日付: 2026-07-28 / 対象: `claude-opus-5`（Claude Code 既定モデル） / 種別: 調査ノート（変更は未適用）

## 要旨

- **仕様面の破壊的変更は2点**: `thinking` の既定が ON、`thinking:disabled` は effort ≤ high でのみ許可。[高]
- **Experiment 005 に未凍結の不整合**: 設計は `claude-opus-4-8` / `effort=high` を凍結候補にしているが、実行環境の実効 effort は全セッション `xhigh`。凍結前のいま直せる。[高]
- **pxpipe allowlist は Opus 5 未計測のまま**。既定モデルが Opus 5 の間、Compression 層は不発。[高]
- **ローカル実測はベンダー文書の挙動傾向（応答が長い・委譲に積極的）を裏付けなかった**。ただし交絡が大きく、否定の証拠にもならない。[中]
- `fable_scan.py` の単価表は `claude-opus-5` を正しく $5/$25 に解決する。**単価バグは無し**。[高]

---

## 1. 公式仕様（確定分）

出典: `claude-api` skill（Current Models 表 cached 2026-06-24 / `shared/model-migration.md` → Migrating to Claude Opus 5 / `shared/models.md` / `shared/prompt-caching.md`）。[高]

| 項目 | 値 | 備考 |
|---|---|---|
| Model ID | `claude-opus-5` | 日付サフィックスなし |
| Context / Max output | 1M（既定かつ最大）/ 128K | |
| 価格 | $5 / $25 per MTok | **Opus 4.8 と同額**。Fable 5 は $10/$50 |
| Prompt cache 最小 | **512 token** | Opus 4.8 は 1024。短いプロンプトが新たにキャッシュ対象になる |
| Rate limit | Opus 4.x 合算プールとは**別バケット** | 4.x から移行しても旧枠は空かず、旧枠を引き継ぎもしない |
| Effort | `low`〜`max`（既定 `high`） | |
| Fast mode | `speed:"fast"`、$10/$50、Claude API のみ | Bedrock / Vertex / Foundry 非対応 |

### 破壊的変更（Opus 4.8 → Opus 5）

1. **`thinking` 省略時の既定が ON**。4.8 / 4.7 は省略＝思考なしだった。`max_tokens` は thinking と応答テキストの**合算**上限なので、4.8 で思考なし前提に `max_tokens` を詰めていた経路は応答が途中で切れうる。
2. **`thinking:{type:"disabled"}` は effort ≤ high でのみ許可**。`xhigh` / `max` との併用は 400。リクエスト単位で検証されるため、途中で effort を上げた1リクエストだけが落ちる。
3. raw chain of thought は返らない（`display:"summarized"` で要約のみ）。

### 挙動シフト（prompt でチューニング可能、API 呼び出し側向けの記述）

- 応答・成果物ファイルが長くなる。**`effort` を下げても可視出力長は縮まない**（プロンプトが唯一のレバー）
- 言われなくても自己検証する → 「検証してから返せ」型 scaffolding は削除が推奨（over-verification を招く）
- **サブエージェント委譲に積極的**（Opus 4.8 は逆に消極的だった）→ 4.8 向けに足した「もっと委譲しろ」系ガイダンスは撤去 + 上限指定が推奨
- 自己訂正の narration が増える / タスクスコープを勝手に広げうる
- `low` / `medium` が想定以上に強い（コスト・レイテンシの主レバー）

> **重要な読み替え**: 上記の挙動シフトは *Claude API を直接叩く実装者* 向けの記述で、対策ブロックを自分でプロンプトに足すことが前提になっている。Claude Code は本セッションの system prompt に既に相当するブロック（`# Corrections` / `# Delivering work` のスコープ規律 / 「When you have enough information to act, act」/ 「Write code that reads like the surrounding code」）を同梱している。[高: 本セッションの system prompt で直接確認]
> したがって Claude Code 上で観測できるのは**対策後の Opus 5** であり、素の API 挙動とは別物として扱う。§3 の実測はこの前提で読む。[中]

---

## 2. ASCS リポジトリへの影響

### 2-1. Experiment 005 の凍結条件（要判断・未適用）

対象: `docs/experiment-005-design.md:77`（frozen fields テーブル）、`:116`（Human Approval Gate）

現状の凍結候補（引用行は 2026-07-28 時点で一致を確認済み）:

```
docs/experiment-005-design.md:77   | model | Opus (`claude-opus-4-8`) |
docs/experiment-005-design.md:116  - the paid runtime and model (`claude-opus-4-8`, high effort, auto mode);
```

`scripts/exp005.py:1075` は `prepare_parser.add_argument("--model", required=True)` で、モデル文字列をハードコードしていない。`tests/test_exp005.py` の `claude-opus-4-8` も fixture 値であり検証対象の定数ではない。**したがってヘルパーの改修は不要で、変更は設計文書の凍結候補のみ**。[高]

**発見した不整合（当初想定していなかった項目）**: ローカル transcript の `effort` フィールドは、観測できた全モデル・全セッションで `xhigh` だった（`fable-5` のみ `max` が 4 件）。[高]

| main モデル | effort 分布 |
|---|---|
| fable-5 | xhigh 12484 / max 4 |
| opus-5 | xhigh 2474 |
| opus-4-8 | xhigh 836 |

Experiment 005 は effort を `high` で凍結し、違反を void condition 7 として扱う設計になっている。**operator が環境の既定のまま arm を開始すると、モデルを正しく選んでも effort だけで void になる**。model の再ピン可否とは独立に、この点は凍結前に解消しておく必要がある。

さらに model を Opus 5 にする場合の追加論点:

- Opus 5 は thinking 既定 ON、Opus 4.8 は既定 OFF。**同じ「effort=xhigh」でも思考の有無が変わりうる**ため、「4 arm すべて同一 runtime 条件」という 005 の前提の意味が model 選択に依存する。[中: 仕様からの推定。Claude Code が thinking を明示指定しているかは未検証]
- 45分/arm・retry 1 のコスト上限は Opus 4.8 前提の見積り。thinking 既定 ON なら消費が変わりうる。[低: 実測なし。arm 1 本を計測して再見積りするのが検証手順]

判断材料（推奨は A、ただし effort の是正が前提）:

| 案 | 内容 | 利点 | 欠点 |
|---|---|---|---|
| **A** | model を `claude-opus-5` に再ピン | 実行環境の既定と一致し、operator の取り違えで void になりにくい | 004 closeout の「Opus を標準 runtime に」は満たすが、4.8 世代との連続性は失う |
| B | `claude-opus-4-8` を維持 | 設計時の想定どおり | arm ごとに明示的なモデル切替が必要で、void condition 7 のリスクが上がる |

`docs/experiment-005-design.md` は PR #15 に載っているため、**このブランチでは編集しない**。差分案は §5 に置く。

### 2-2. pxpipe allowlist と R1（要判断・未適用）

対象: `docs/claude-code/pxpipe-safety.md:7,38`、`docs/hook-responsibilities.md:64`、`docs/architecture.md:179`、`docs/risk-register.md` R1、`README.md:264` / `README.ja.md:248`（全て 2026-07-28 時点で引用一致を確認）

- 除外の根拠は **Opus 4.8 の実測**（dense image 内 12 文字 hex 正読 0/15、Fable 5 は 13/15）。`PXPIPE_MODELS` 既定は `claude-fable-5,gpt-5.6`
- **Opus 5 の誤読率は上流にも当リポジトリにも実測が無い（未検証）**。現在の記述は 4.8 の実測を Opus 系全体へ外挿している
- 帰結: 既定モデルが Opus 5 で allowlist が既定のままなら、圧縮リクエストは発生しない。**Compression 層は不発**（安全側だが、スタックの効果測定という観点では 1 層が死んでいる）

推奨: **allowlist は広げない**（fail-safe 側を維持）。ただし記述を「4.8 の実測」と「Opus 5 は未計測」に分離し、外挿であることを明示する。R1 の確度タグも同様に分ける。

Opus 5 を実測する場合は上流 pxpipe の hex テストが必要で、課金・外部依存が絡む。**本ノートの範囲外**。実施するなら別途 Human Approval Gate（expensive_api）を通す。

---

## 3. ローカル transcript の実測

### 3-1. 手順（再現可能）

```bash
# モデル別ロールアップ
python3 ~/.claude/scripts/usage_by_session.py 2026-07-01T00:00:00+09:00

# main モデル別プロファイル（本ノート用に作成、scratchpad 内・リポジトリ外）
python3 main_model_profile.py 2026-07-01
```

`main_model_profile.py` の判定規則:
- `~/.claude/projects/*/<session>.jsonl` を走査、`isSidechain=True` は除外、`requestId` で重複排除
- セッションの主モデル = main で最もリクエスト数が多いモデル。**主モデルが 80% 未満の混在セッションは除外**（358 → 346 セッション）
- サブエージェント起動は **`Agent` ツール**の `tool_use` ブロック数。`TaskCreate` / `TaskUpdate` は TODO 管理用で無関係（当初 `Task` で数えて 0 件になった誤りを訂正済み）

### 3-2. 結果（2026-07-01 以降）

| main モデル | sess | req | req/sess | out/req | Agent/100req | subfile/sess | write/100req |
|---|---|---|---|---|---|---|---|
| fable-5 | 255 | 18769 | 74 | 1124 | 4.3 | 3.1 | 39.0 |
| opus-4-8 | 35 | 2092 | 60 | 992 | 3.9 | 2.0 | 31.4 |
| **opus-5** | **30** | **1155** | **38** | **945** | **2.2** | **0.5** | **23.3** |
| sonnet-5 | 5 | 732 | 146 | 921 | 1.9 | 1.6 | 31.7 |

観測期間:

| main モデル | first_ts 〜 last_ts |
|---|---|
| fable-5 | 2026-07-01T20:20 〜 2026-07-27T11:09 |
| opus-4-8 | 2026-07-01T22:22 〜 2026-07-20T05:50 |
| **opus-5** | **2026-07-25T06:17 〜 2026-07-27T22:24（3日間）** |
| sonnet-5 | 2026-07-11T00:37 〜 2026-07-13T12:16 |

### 3-3. 読み取り

**ベンダー文書の挙動傾向2件について、ローカルデータは裏付けを与えなかった。**[中]

- 「応答が長くなる」: opus-5 の out/req は 945 で、opus-4-8 の 992 を**下回る**
- 「サブエージェント委譲に積極的」: opus-5 の Agent/100req は 2.2 で、opus-4-8 の 3.9 を**下回る**。req で正規化しても subfile は opus-5 0.013/req < opus-4-8 0.033/req

**ただしこれは「傾向が存在しない」ことの証拠にはならない。** 交絡が大きい:

1. **対策後の観測である**（§1 の読み替え）。Claude Code の system prompt は既に冗長化・スコープ拡大・自己訂正 narration の抑制ブロックを含む。ベンダー文書の傾向は「対策を入れていない場合」の記述
2. **`guard-builtin-agent-model.sh` hook** が組み込みエージェントの model 未指定起動をブロックしており、委譲そのものに摩擦がある（本セッションでも発火）
3. **観測期間・規模が非対称**。opus-5 は 3日間・30セッション・1155 req のみ。opus-4-8 は 20日間
4. **タスク種が統制されていない**。opus-5 セッションは短い（38 req/sess vs 60）ため、タスクの性質自体が違う可能性が高い

**主張の境界**（`docs/claim-boundary-model.md` と Experiment 004 closeout に従う）: 上表から言えるのは**観測された使用構成の記述**のみ。モデル優劣・生産性・速度の主張はしない。treated/baseline 比較でもない。

### 3-4. 副次的な確認結果

- `fable_scan.py:46` の `price_key()` は substring 一致（`if "opus" in model`）なので `claude-opus-5` は正しく `opus` 単価（$5/$25）に解決される。**単価バグは無し**、`unknown_models` にも計上されない。[高]
- `usage_by_session.py` にはコスト列が無い（トークンのみ）。当初の調査計画では単価表を持つと想定していたが誤りで、単価表は `fable_scan.py` 側にのみ存在する。[高]

---

## 4. 運用ルール（`~/.claude/CLAUDE.md`）— 結論: 現時点で変更不要

**読み取りのみ。編集していない。**

| 箇所 | 内容 | 判定 |
|---|---|---|
| L58 | 「独立したサブタスクは並列で委譲し…」 | **変更しない**。ベンダー文書だけなら上限追加の候補だが、§3 の実測では opus-5 の委譲はむしろ少ない。実測に反する変更は入れない |
| L291（Claude Code profile） | 「独立サブタスクの並列委譲は…積極活用する」 | 同上 |
| L23 / L191 | 「進捗・完了はツール実行結果で実証」「根拠を指せない事項は未検証と明示」 | **維持**。これは自己検証 scaffolding ではなく*捏造防止の証拠規律*であり、Opus 5 の自己検証能力では代替できない。削除候補ではない |
| `~/.claude/hooks/guard-builtin-agent-model.sh` | 組み込みエージェントの model 明示強制 | **維持**。Opus 5 でも有効に発火（本セッションで実績あり） |

「検証してから返せ」型の over-verification を招く記述は grep で見つからなかった。[高]

再評価の条件: opus-5 の main セッションが 100 本程度たまった時点で §3 の集計を再実行し、Agent/100req が opus-4-8 を上回っていれば L58 / L291 に上限を足すことを再検討する。

---

## 5. 差分案（**未適用**。適用にはそれぞれ個別の承認が必要）

### 5-1. `docs/experiment-005-design.md`（PR #15 と衝突するため本ブランチでは触らない）

```diff
-| model | Opus (`claude-opus-4-8`) |
+| model | Opus (`claude-opus-5`) |
-| reasoning effort | high |
+| reasoning effort | xhigh（実行環境の既定と一致させる。high で凍結する場合は arm 開始前に明示的な切替と記録が必要） |
```

`:116` の Human Approval Gate 記述も同じモデル名・effort に揃える。

### 5-2. `docs/claude-code/pxpipe-safety.md:38` ほか

```diff
-| Model allowlist | `PXPIPE_MODELS` (default: `claude-fable-5,gpt-5.6`) | only allowlisted models get imaged requests; models with high misread rates (Opus 4.7/4.8, GPT 5.5) are excluded by default — don't widen this |
+| Model allowlist | `PXPIPE_MODELS` (default: `claude-fable-5,gpt-5.6`) | only allowlisted models get imaged requests; models with measured high misread rates (Opus 4.7/4.8, GPT 5.5) are excluded by default. Opus 5 has **no measurement** — it is excluded by extrapolation from 4.8, which also means compression does not engage when Opus 5 is the session model. Don't widen this |
```

`docs/hook-responsibilities.md:64`、`docs/architecture.md:179`、`README.md:264` / `README.ja.md:248` も「Opus 4.8 の実測」と「Opus 5 は未計測」を分離する。

`docs/risk-register.md` R1 の確度欄:

```diff
-| [高] README 明記 |
+| [高] README 明記（Opus 4.8 の実測）／ Opus 5 は未計測・外挿 |
```

### 5-3. `~/.claude/CLAUDE.md`

**変更提案なし**（§4）。

---

## 6. 未検証・残リスク

| # | 項目 | 状態 | 検証手順 |
|---|---|---|---|
| 1 | Opus 5 の pxpipe 画像内 hex 誤読率 | **未検証** | 上流 pxpipe の hex テストを Opus 5 で実行。課金・外部依存のため Human Approval Gate（expensive_api）が必要 |
| 2 | Claude Code が `thinking` を明示指定しているか | **未検証** | 4.8 arm と 5 arm で思考の有無が揃うかに関わる。transcript には thinking 設定が出ないため、判定にはリクエスト側の観測が要る |
| 3 | Opus 5 の thinking 既定 ON がコスト上限（45分/arm）に与える影響 | **未検証** | Experiment 005 の arm を 1 本計測して再見積り |
| 4 | §3 の傾向差がモデル由来か、タスク種・期間由来か | **分離できていない** | 統制不能。opus-5 セッション蓄積後に再集計し、方向が変わるかを見る |
| 5 | Experiment 005 の frozen effort（high）と実行環境（xhigh）の不整合 | **未解消** | §5-1 の差分を適用するか、arm 開始手順に effort 切替を明記する |

## 7. 参照

- 公式仕様: `claude-api` skill（`shared/models.md` / `shared/model-migration.md` → Migrating to Claude Opus 5 / `shared/prompt-caching.md`）
- リポジトリ: `docs/experiment-005-design.md`、`docs/claude-code/pxpipe-safety.md`、`docs/risk-register.md`、`docs/claim-boundary-model.md`、`experiments/2026-07-06-claude-code-restart-004-closeout.md`
- 集計スクリプト: `~/.claude/scripts/usage_by_session.py`、`~/.claude/scripts/fable_scan.py`、本ノート用 `main_model_profile.py`（scratchpad、リポジトリ外）
