<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 学習・保守ロードマップ

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## Day 1: 起動と全体像

1. install候補: install command未検出
2. 最初の実行/検査: `検証command未検出`
3. `scripts` を読み、CLI・バッチ・運用入口の境界を確認


## Day 2–3: 主要契約

- APIがない/未検出であることを確認
- `scripts/exp004.py` の 1 entityとmigration順序を確認
- CLI/API/docs入口の成功・失敗フィードバックを確認
- external/config: 外部integration未検出 / CLAUDE_CONFIG_DIR, CLAUDE_PROJECT_DIR, TMPDIR, ANTHROPIC_BASE_URL, PATH

## 最初の変更前

- 変更対象に最も近いtest: `tests/test_exp004.py`, `tests/test_exp005.py`, `tests/test_ascs.py`, `tests/test_check_state.py`, `tests/test_validate_repo.py`, `tests/test_compact_plus_smoke.py`, `tests/test_ascs_doctor.py`, `tests/test_exp003.py`
- 既存ADR/docs: `README.md`, `README.ja.md`, `plugins/ascs/README.md`, `experiments/README.md`, `experiments/2026-07-06-claude-code-restart-004-shared-scaffold/README.md`, `experiments/2026-07-11-claude-code-restart-005-shared-scaffold/README.md`, `docs/hook-responsibilities.md`, `docs/architecture.md`, `docs/user-guide.ja.md`, `docs/claude-code-reference-integration.md`, `docs/measurement-harness.md`, `docs/acceptance-criteria.md`
- runtime: config (`.github/workflows/test.yml`)
- `07_traceability.md` の未確認事項をcloseまたはrisk acceptしてから変更する。

## Doneの定義

- build/type/lint/testのうち存在するgateが通る。
- API/data/UI/runtimeの変更に対応する文書とADRを更新する。
- rollback、秘密情報、外部送信、production影響をreviewで明示する。
