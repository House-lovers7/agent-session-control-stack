# Acceptance Criteria

> Phase 0 設計原本。「統合が成立している」と言える条件をフェーズ別に定義する。

## Phase 1（docs-only）の受け入れ基準

Status: **accepted on 2026-07-16** by repository validation, pinned-source
review, attribution audit, and current official hook-spec review. Phase 2 is
separate and remains incomplete.

### 事実性
- [x] 3 OSS に関する仕様記述がすべて Phase 0 設計原本（検証済み事実）と一致し、憶測仕様が 1 つもない
- [x] pxpipe について「カテゴリ別除外は npx 運用では不可」が明記され、存在しない安全設定を示唆する記述がない
- [x] compact-plus の LLM バックエンドが課金 API であることと、`""` でのスキップが明記されている
- [x] session-health の実測値（66% / 233x→83x）を引用する場合、「因果ではなく整合性の証拠」という作者の留保ごと引用している

### 構造
- [x] Compression / Health / Checkpoint / Recovery の 4 層で全ドキュメントが一貫している
- [x] compact 提案の意思決定者が session-health 1 つであること、その実現方法（warn-marker 生成器を導入しない）が説明されている
- [x] Claude Code 固有実装と Codex 汎用実装が別ドキュメント・別ディレクトリに分かれている
- [x] 未検証点と撤退基準が README から 1 クリックで到達できる

### 姿勢
- [x] README 冒頭に「3 OSS を置き換えない」宣言がある
- [x] ATTRIBUTION.md に 3 作者（teamchong / House-lovers7 / u-ichi）のクレジットがある
- [x] 3 OSS のコードを 1 行もコピーしていない

### 実体の妥当性
- [x] examples/claude-code/settings.example.json が有効な JSON で、env 変数名がすべて実在（`SESSION_HEALTH_*` / `COMPACT_PLUS_*` / `PXPIPE_*`）
- [x] examples/codex/AGENTS.md が単体で protocol として自己完結（state 読取 → checkpoint → handoff → recovery）
- [x] templates/state-file.md が compact-plus の 10 セクションと同名・同順
- [x] 内部リンクがすべて解決する

## Phase 2（検証）の受け入れ基準

「効いている」と言える最低条件（measurement-plan.md の指標で判定）:

- [ ] compact 後の再開時、要約のみに基づく誤った前提での作業着手（迷走）が baseline より減る
- [ ] 却下済みアプローチの再提案が baseline より減る
- [x] compact 提案がセッション中に二重化しない（session-health 以外から「畳め」が出ない）ことをログで確認（Dogfood 0.2の1セッション。効果の証拠ではない）
- [ ] Codex: checkpoint 更新トリガー該当時の実施率が記録されている（値自体は問わない。測れていることが基準）
- [x] pxpipe 有効セッションで byte-exact 値の silent confabulation 事故が 0 件（Dogfood 0.2の観測範囲。発生したら即 `PXPIPE_DISABLE=1` で切り、記録する）

## 明確に受け入れ基準にしないもの

- 使用量上限（rate limit / 使用率表示)の改善 — 上限の算定方法が非公開のため、入力トークン削減が使用率に比例して効くとは言えない
- 因果の証明 — n が小さく統制もないため、Phase 2 は整合性の証拠まで
