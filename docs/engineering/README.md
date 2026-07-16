<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — Engineering Handbook / Start Here

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 60分で把握する

1. コンセプト: 長時間AIコーディングエージェント運用をCompression/Health/Checkpoint/Recoveryへ分離し、Claude Codeはupstream plugins、Codexはnative hooks + portable state protocolで実装するreference stack。
2. classification: `active_project` / stack: Python標準ライブラリ中心のCLI・hook・docs
3. install: READMEのClaude marketplace手順、またはCodex exampleの手動copy/merge
4. run/check: `python3 -m unittest discover tests -v`、`python3 scripts/validate_repo.py --require-upstream-lock`
5. entrypoint: `scripts/ascs.py`、`scripts/check_state.py`、`plugins/ascs/scripts/ascs_doctor.py`、Codex compact hook example

## 実装スナップショット

| 項目 | 現在値 | 最初に読むpath |
|---|---:|---|
| package/component | 1 | `scripts` |
| API | 0 | 未検出 |
| entity | 1 | `scripts/exp004.py` |
| screen/entry UI | 0 | 未検出 |
| test files | 9 | `tests/test_codex_compact_hook.py` |

## 最初に確認する既存の正典候補

- `README.md`
- `README.ja.md`
- `plugins/ascs/README.md`
- `experiments/README.md`
- `experiments/2026-07-06-claude-code-restart-004-shared-scaffold/README.md`
- `experiments/2026-07-11-claude-code-restart-005-shared-scaffold/README.md`
- `docs/hook-responsibilities.md`
- `docs/architecture.md`
- `docs/user-guide.ja.md`
- `docs/claude-code-reference-integration.md`
- `docs/measurement-harness.md`
- `docs/acceptance-criteria.md`
- `docs/improvement-loop.md`
- `docs/state-trust-contract.md`
- `docs/upstream-compatibility.md`
- `docs/experiment-004-design-draft.md`
- `docs/user-guide.md`
- `docs/implementation-plan.md`
- `docs/claim-boundary-model.md`
- `docs/when-not-to-use.md`
- `docs/case-study-dogfood-0.2.md`
- `docs/compact-plus-synthetic-smoke.md`
- `docs/risk-register.md`
- `docs/adapter-interface.md`
- `docs/experiment-005-design.md`
- `docs/measurement-plan.md`
- `docs/experiment-003-design.md`
- `docs/measurement-checklist.md`
- `docs/agent-session-control-stack.md`
- `docs/claude-code/recommended-stack.md`

既存ADR、OpenAPI、schema、運用runbookがある場合は、下記generated docsより先に読む。

## 引継ぎblocking / partial

| Priority | Requirement | 状態・理由 | Evidence |
|---|---|---|---|
| P1 | `codex_runtime_smoke` | native hookのfocused testはあるが、実Codex manual/auto compact dispatchは未検証。 | `docs/codex/adapter-design.md` |
| P1 | `composition_efficacy` | mechanism smokeはあるが、生産性・速度・費用・品質の改善効果は未実証。 | `README.md` |

## 読む順番

1. [One Pager](./00_one_pager.md)
2. [技術スタック比較](./01_stack_comparison.md)
3. [アーキテクチャ・システム構成](./02_architecture.md)
4. [ADR](./03_adrs/ADR-0001-current-implementation-baseline.md)
5. [API定義](./04_api.md)
6. [データモデル・ER図](./05_data_model.md)
7. [非機能要件・SLO/SLI](./05_nfr_slo.md)
8. [画面設計](./06_screen_design.md)
9. [P50/P90見積り](./06_estimation.md)
10. [実装トレーサビリティ](./07_traceability.md)
11. [学習・保守ロードマップ](./08_learning_roadmap.md)

## 使い方

- generated docsは実装発見用handbook。既存ADR、OpenAPI、schema、runbookがある場合は既存正典を優先する。
- path・数・versionは静的検出した事実。目的やpath由来の責務は `[中]` の推定を含む。
- production、external console、secret値、migration適用状態は未確認。
