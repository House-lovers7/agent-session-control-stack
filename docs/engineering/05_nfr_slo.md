<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 非機能要件・SLO/SLI

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 現在コード化されている品質ゲート

| Gate | Command | 根拠 |
|---|---|---|
| unit | `python3 -m unittest discover tests -v` | `.github/workflows/test.yml` |
| repository validation | `python3 scripts/validate_repo.py --require-upstream-lock` | `.github/workflows/test.yml` |

- test files: 9（Codex native compact hookを含む）
- quality/CI config: `.github/workflows/test.yml`
- security/resilience signals: Doctorのsecret非表示・version/content fail-closed、state metadata/secret検査、Codex hookのsession一致・one-shot・fail-open、evidence schema拒否test

## 計測すべきSLI

| Boundary | SLI | 最初の計測根拠 |
|---|---|---|
| Codex hook | Pre/PostCompact発火率、one-shot消費率、fail-open率 | `tests/test_codex_compact_hook.py` |
| Evidence | malformed/void evidence拒否率、claim境界 | `tests/test_ascs.py` |

## SLOの状態

[高] 合意済みSLO数値はrepository内の実装・資料から確認できていない。任意の99%や2秒を現在要件として記載しない。利用者、運用時間帯、障害コスト、予算を確認してから、上記SLIごとにtarget/window/error budgetを決める。

## 運用境界

- runtime/config: config (`.github/workflows/test.yml`)
- required config names: CLAUDE_CONFIG_DIR, CLAUDE_PROJECT_DIR, TMPDIR, ANTHROPIC_BASE_URL, PATH
- 外部integration: 静的検出なし
- rollbackはcode、schema、generated artifact、provider設定を分ける。production操作は人間承認後に行う。
