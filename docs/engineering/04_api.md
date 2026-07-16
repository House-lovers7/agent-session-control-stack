<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — API定義書

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。


## Public interface inventory

- CLI/script: `scripts/ascs.py`, `scripts/check_state.py`, `scripts/exp003.py`〜`exp005.py`
- plugin command: `/ascs:doctor`
- lifecycle hook: `examples/codex/.codex/hooks/ascs_compact.py`
- HTTP endpoints: 0

## 検出したAPI

HTTP APIは製品スコープ外。公開契約はCLI引数・exit code、plugin command出力、hook JSON stdin/stdoutである。

## API所有境界

- CLI: `scripts/`
- Claude plugin: `plugins/ascs/`
- Codex hook example: `examples/codex/.codex/`

## 実装から確認できた追加契約

- 追加のmultipart・上限・副作用signalは静的検出できず。実装とcontract testを確認する。

## CLI契約

- `scripts/ascs.py`: doctor/init/record/finish/score/measure
- `scripts/check_state.py`: 0=pass/absent、1=invalid/unsafe、2=stale
- Codex hook: JSON stdin、fail-open `continue: true`、compact SessionStartでdocumented additionalContext

## 変更時の実務チェック

- caller: UI caller未検出。CLI/job/external callerを検索
- schema: route内inline validationだけでなく共有schema・型・OpenAPIの有無を確認する。
- auth: `未確認` のendpointは公開を意味しない。middleware、gateway、provider側設定も確認する。
- error: 表中にstatus signalがないhandlerは、成功/入力/権限/依存障害の契約をtestで固定する。
- write: POST/PUT/PATCH/DELETEは冪等性、重複retry、監査ログ、rollbackを確認する。

## 未確認

- 動的に登録されるroute、gateway rewrite、provider callback、production側rate limit。
- request/responseの完全なfield定義は、表の実装pathと共有schemaを正典として確認する。
