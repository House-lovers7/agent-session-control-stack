# Codex 向け AGENTS.md 案 + checkpoint/handoff protocol

> Phase 0 設計原本。Codex には Claude Code の compact lifecycle が無い前提で、Checkpoint / Recovery 層を **session handoff protocol** として実装する。「compact 対策」ではなく「セッションをまたぐ作業引き継ぎの規約」として提示する。

## 1. ファイルレイアウト

```
<target repo>/
  AGENTS.md                     # session protocol を宣言（下記 §2）
  .agent-session/
    state/
      current-plan.md           # いま何をどの順でやるか（承認済み plan）
      decision-log.md           # 採用/却下した選択肢と理由
      failed-attempts.md        # 失敗したアプローチ・コマンド・原因仮説
      recovery-notes.md         # 再開時に読むべき注意（罠・環境固有事情）
      checkpoint.md             # 最新の 10 セクション状態スナップショット
    handoff.md                  # 次セッションへの引き継ぎ（唯一の再開入口）
```

- `.agent-session/` は `.gitignore` 推奨（作業ログであり、プロダクト正史ではない）
- `checkpoint.md` のスキーマは templates/state-file.md（10 セクション、compact-plus 互換）を使う。Claude Code 側と同一スキーマにすることで、runtime をまたぐ handoff（Claude Code → Codex）も同じファイルで成立する

## 2. AGENTS.md に入れる protocol（英語・そのまま貼れる版）

```markdown
## Session Control Protocol

### Before starting work
- Read .agent-session/handoff.md first if it exists. It is the single entry
  point for resuming; treat any summary in it as a hypothesis and verify
  against the referenced files before acting on it.
- Read .agent-session/state/current-plan.md if it exists.
- Read .agent-session/state/decision-log.md before changing architecture
  or reversing a prior decision.
- Read .agent-session/state/failed-attempts.md before retrying an approach.

### During long work
- Update state/decision-log.md when choosing or rejecting an approach.
- Update state/failed-attempts.md after failed commands, rejected plans,
  or repeated errors — include the cause hypothesis, not just the failure.
- Refresh state/checkpoint.md at natural boundaries: after completing a
  phase, before a risky or wide-ranging change, and roughly every 10
  substantial steps (file edits, test runs, tool calls).
- Keep bulky content (long logs, full file dumps, raw tool output) out of
  state files; reference paths instead.

### Before stopping, switching models, or starting a new session
- Update .agent-session/handoff.md: goal, current phase, next action,
  open risks, and pointers to the state files. Assume the reader has
  zero memory of this session.

### Before destructive actions
- Ask for human approval.
- Confirm deploy target, branch, migration name, and rollback plan as
  exact text — never from memory or summaries.
```

## 3. Checkpoint protocol（いつ・何を）

| トリガー | 書く先 | 内容 |
|---|---|---|
| 選択肢を採用/却下した | decision-log.md | 選択肢・決定・理由・却下理由（1 決定 1 エントリ） |
| コマンド失敗・アプローチ放棄・同種エラー 2 回目 | failed-attempts.md | 何を試し、何が起き、原因仮説は何か |
| フェーズ完了 / 危険な変更の直前 / 実質 10 ステップごと | checkpoint.md | 10 セクション全体を上書き更新 |
| セッション終了・モデル切替・中断 | handoff.md | goal / phase / next action / risks / state への参照 |

Health 層の代理シグナル（Codex には transcript メトリクスが無い）:

- 経過時間が長い / tool call・編集ファイル数が積み上がった / テスト失敗が反復している / diff が大きく育った — これらを感じたら checkpoint.md を更新し、区切りが良ければ handoff を書いて新セッションを検討する
- 数値閾値による自動化（wrapper `codex-session run` が usage / diff / 失敗回数を監視して checkpoint を促す）は Phase 2+。Phase 1 では protocol 文言のみで運用し、遵守率を測る

## 4. Recovery protocol（新セッション再開手順）

1. `handoff.md` を読む（無ければ `state/checkpoint.md` → `current-plan.md` の順）
2. handoff / checkpoint の記述は**仮説**として扱い、参照されている実ファイル（plan、対象コード、テスト結果）で裏取りしてから作業に入る
3. `failed-attempts.md` にあるアプローチを再提案しない。再試行する場合は「前回と何を変えるか」を decision-log に書いてから
4. 再開後最初の実質的作業の前に checkpoint.md を一度更新する（読み込んだ理解の宣言 = 認識ズレの早期検出）

## 5. Skills（Phase 1 での任意追加）

protocol を確実に踏ませるため、Codex の Agent Skills として 2 つを切り出せる:

- `session-checkpoint`: §3 の手順を対話的に実行（10 セクションを聞き取り・生成して checkpoint.md を更新）
- `session-recovery`: §4 の手順を実行（handoff → state → 裏取り → 理解の宣言）

Skills 化は必須ではない。AGENTS.md の protocol 文言だけでも成立する設計とし、Skills は遵守率を上げる補助と位置づける。

## 6. Claude Code binding との対応（同じ契約・別の面）

| 契約 | Claude Code（自動・hook） | Codex（手続き・protocol） |
|---|---|---|
| Checkpoint | compact-plus PreCompact が LLM で state file 生成 | エージェント自身が checkpoint.md を更新 |
| Recovery | PostCompact marker → 次プロンプトで自動注入 | handoff.md を読む規約 + 仮説扱いの明文化 |
| Health | session-health が transcript を実測 | 代理シグナル + 自己申告（弱い実装であることを明記） |
| Compression | pxpipe proxy | 移植しない。「bulky content を state に入れない」運用規律のみ |
