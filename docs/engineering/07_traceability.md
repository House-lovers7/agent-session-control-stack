<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 実装トレーサビリティ

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 根拠台帳

| 種別 | Path | 状態 |
|---|---|---|
| package/source | `scripts` | 静的確認済み |
| data | `scripts/exp004.py` | 静的確認済み |
| data | `scripts/exp005.py` | 静的確認済み |
| test | `tests/test_exp004.py` | 静的確認済み |
| test | `tests/test_exp005.py` | 静的確認済み |
| test | `tests/test_ascs.py` | 静的確認済み |
| test | `tests/test_check_state.py` | 静的確認済み |
| test | `tests/test_validate_repo.py` | 静的確認済み |
| test | `tests/test_compact_plus_smoke.py` | 静的確認済み |
| test | `tests/test_ascs_doctor.py` | 静的確認済み |
| test | `tests/test_exp003.py` | 静的確認済み |
| test | `tests/test_codex_compact_hook.py` | 静的確認済み |
| quality/CI | `.github/workflows/test.yml` | 静的確認済み |
| existing docs | `README.md` | 静的確認済み |
| existing docs | `README.ja.md` | 静的確認済み |
| existing docs | `plugins/ascs/README.md` | 静的確認済み |
| existing docs | `experiments/README.md` | 静的確認済み |
| existing docs | `experiments/2026-07-06-claude-code-restart-004-shared-scaffold/README.md` | 静的確認済み |
| existing docs | `experiments/2026-07-11-claude-code-restart-005-shared-scaffold/README.md` | 静的確認済み |
| existing docs | `docs/hook-responsibilities.md` | 静的確認済み |
| existing docs | `docs/architecture.md` | 静的確認済み |
| existing docs | `docs/user-guide.ja.md` | 静的確認済み |
| existing docs | `docs/claude-code-reference-integration.md` | 静的確認済み |
| existing docs | `docs/measurement-harness.md` | 静的確認済み |
| existing docs | `docs/acceptance-criteria.md` | 静的確認済み |
| existing docs | `docs/improvement-loop.md` | 静的確認済み |
| existing docs | `docs/state-trust-contract.md` | 静的確認済み |
| existing docs | `docs/upstream-compatibility.md` | 静的確認済み |
| existing docs | `docs/experiment-004-design-draft.md` | 静的確認済み |
| existing docs | `docs/user-guide.md` | 静的確認済み |
| existing docs | `docs/implementation-plan.md` | 静的確認済み |
| existing docs | `docs/claim-boundary-model.md` | 静的確認済み |
| existing docs | `docs/when-not-to-use.md` | 静的確認済み |
| existing docs | `docs/case-study-dogfood-0.2.md` | 静的確認済み |
| existing docs | `docs/compact-plus-synthetic-smoke.md` | 静的確認済み |
| existing docs | `docs/risk-register.md` | 静的確認済み |
| existing docs | `docs/adapter-interface.md` | 静的確認済み |
| existing docs | `docs/experiment-005-design.md` | 静的確認済み |
| existing docs | `docs/measurement-plan.md` | 静的確認済み |
| existing docs | `docs/experiment-003-design.md` | 静的確認済み |
| existing docs | `docs/measurement-checklist.md` | 静的確認済み |
| existing docs | `docs/agent-session-control-stack.md` | 静的確認済み |
| existing docs | `docs/claude-code/recommended-stack.md` | 静的確認済み |

## 検出した検証command

- `python3 -m unittest discover tests -v`
- `python3 scripts/validate_repo.py --require-upstream-lock`
- `python3 scripts/ascs.py doctor`

## 設定契約（名前のみ）

- `CLAUDE_CONFIG_DIR` — `plugins/ascs/scripts/ascs_doctor.py`
- `CLAUDE_PROJECT_DIR` — `plugins/ascs/scripts/ascs_doctor.py`
- `TMPDIR` — `plugins/ascs/scripts/ascs_doctor.py`
- `ANTHROPIC_BASE_URL` — `plugins/ascs/scripts/ascs_doctor.py`
- `PATH` — `scripts/smoke_compact_plus.py`

値、credential、顧客データは収集していない。設定のrequired/optional、format、取得元は各entrypointとruntimeで確認する。

## 既存文書との関係

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
- `docs/claude-code/pxpipe-safety.md`
- `docs/codex/adapter-design.md`
- `docs/codex/agents-md-draft.md`
- `docs/implementation-notes/2026-07-10-doctor-ci-hardening.md`
- `docs/implementation-notes/2026-07-10-upstream-state-experiment-hardening.md`
- `docs/implementation-notes/2026-07-10-evidence-boundaries.md`
- `examples/claude-code/stack-demo/README.md`
- `examples/claude-code/stack-demo/hooks/README.md`

既存ADR・公式schema・運用runbookがある場合はそれらを正典とし、generated docsは発見用索引として扱う。矛盾を見つけたら実装・正式文書・生成器のどれを直すかをreviewで決める。

## 未確認事項

- 動的route/schema/plugin、external gateway、mobile native設定。
- secret manager、provider console、production runtimeの値と適用version。
- migration適用状態、SLO実績、実データ量、owner/on-call。

## 更新ルール

- route/schema/screen/runtime構成を変更した差分では、対応する文書を同時更新する。
- 生成し直す前に手書き文書を正典へ昇格するか、生成対象外へ分離する。
- このディレクトリの `generated-by` marker付きファイルは本スクリプトで再生成できる。
