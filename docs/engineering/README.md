<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — Engineering Handbook / Start Here

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 60分で把握する

1. コンセプト: 長時間AIコーディングエージェント運用の参照アーキテクチャmeta-repo。pxpipe/session-health/compact-plusを置き換えずCompression/Health/Checkpoint/Recoveryの4層に責務分離し、Claude Codeはhooks/plugin、CodexはAGENTS.md+state+handoff protocolで実装する設計を文書化。コード非同梱・docs-only。
2. classification: `active_project` / stack: runtime未特定
3. install: install command未検出
4. run/check: manifest script未検出
5. entrypoint: entrypoint未検出

## 実装スナップショット

| 項目 | 現在値 | 最初に読むpath |
|---|---:|---|
| package/component | 1 | `scripts` |
| API | 0 | 未検出 |
| entity | 1 | `scripts/exp004.py` |
| screen/entry UI | 0 | 未検出 |
| test files | 8 | `tests/test_exp004.py` |

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
| P1 | `entrypoints` | missing: 実行entrypointを特定できない。資料/資産なら「実行物なし」の明記が必要。 | `docs/engineering/README.md` |
| P1 | `major_modules_and_packages` | partial: package/moduleはあるが、責務、依存方向、公開境界、影響範囲が不足。 | `config/` |
| P1 | `observability` | missing: 可観測性の実装証拠を特定できない。生成文書の一般要件・提案は現行実装の証拠ではない。 | `ATTRIBUTION.md` |
| P1 | `startup_and_verification_commands` | missing: 起動・検証commandを静的証拠から特定できず、生成文書にも実行可能な手順がない。 | `README.md` |

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
