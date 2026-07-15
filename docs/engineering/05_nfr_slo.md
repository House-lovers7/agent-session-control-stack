<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 非機能要件・SLO/SLI

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 現在コード化されている品質ゲート

| Gate | Command | 根拠 |
|---|---|---|
| validation | 未検出 | README/CIで正典を確定 |

- test files: 8（`tests/test_exp004.py`, `tests/test_exp005.py`, `tests/test_ascs.py`, `tests/test_check_state.py`, `tests/test_validate_repo.py`, `tests/test_compact_plus_smoke.py`, `tests/test_ascs_doctor.py`, `tests/test_exp003.py`）
- quality/CI config: `.github/workflows/test.yml`
- security/resilience signal: auth/session (`plugins/ascs/scripts/ascs_doctor.py`), resilience (`plugins/ascs/scripts/ascs_doctor.py`), auth/session (`tests/test_exp004.py`), tenant/RLS (`tests/test_exp004.py`), auth/session (`tests/test_exp005.py`), tenant/RLS (`tests/test_exp005.py`), auth/session (`tests/test_ascs.py`), auth/session (`tests/test_check_state.py`), auth/session (`tests/test_validate_repo.py`), auth/session (`tests/test_ascs_doctor.py`), resilience (`tests/test_ascs_doctor.py`), auth/session (`tests/test_exp003.py`), tenant/RLS (`tests/test_exp003.py`), auth/session (`docs/architecture.html`), auth/session (`scripts/exp003.py`), tenant/RLS (`scripts/exp003.py`), auth/session (`scripts/exp004.py`), tenant/RLS (`scripts/exp004.py`), auth/session (`scripts/exp005.py`), tenant/RLS (`scripts/exp005.py`)

## 計測すべきSLI

| Boundary | SLI | 最初の計測根拠 |
|---|---|---|
| Data | migration成功・constraint違反・鮮度/欠損 | `scripts/exp004.py` |

## SLOの状態

[高] 合意済みSLO数値はrepository内の実装・資料から確認できていない。任意の99%や2秒を現在要件として記載しない。利用者、運用時間帯、障害コスト、予算を確認してから、上記SLIごとにtarget/window/error budgetを決める。

## 運用境界

- runtime/config: config (`.github/workflows/test.yml`)
- required config names: CLAUDE_CONFIG_DIR, CLAUDE_PROJECT_DIR, TMPDIR, ANTHROPIC_BASE_URL, PATH
- 外部integration: 静的検出なし
- rollbackはcode、schema、generated artifact、provider設定を分ける。production操作は人間承認後に行う。
