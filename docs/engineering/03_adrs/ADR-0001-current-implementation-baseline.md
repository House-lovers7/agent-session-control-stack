<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — ADR-0001 現行アーキテクチャ選択

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## Status

Observed / Accepted as current implementation baseline — 2026-07-15

## Context

`agent-session-control-stack` の後発担当者が、現行コードに埋め込まれた選択を暗黙知のまま変更しないよう、観測できる選択と境界を記録する。当時の会議・採用理由が既存ADRにない項目は「Observed」として扱う。

## Decision

| Decision area | Current decision | Evidence |
|---|---|---|
| Code boundary | scripts | `package/source layout` |
| Data boundary | 1 entitiesをschema/migrationで管理 | `scripts/exp004.py, scripts/exp005.py` |
| Quality gate | 8 test files / 1 quality configs | `.github/workflows/test.yml` |

- 上表を次の設計変更までのbaselineとする。
- 既存ADRがある場合はそちらを優先し、このADRは索引・現況記録として扱う。
- framework、schema、配備単位、外部providerを変更する際は新しいADRで代替案と移行・rollbackを記録する。

## Consequences

- 変更影響: `scripts` の境界を跨ぐ変更はAPI/data/UI文書を同時更新する。
- 運用影響: `config (`.github/workflows/test.yml`)` の変更は検証とrollback確認が必要。
- 未確認: production設定、動的route、外部console、secret値、当初の比較検討理由。

## Evidence

- `scripts/exp004.py`
- `scripts/exp005.py`
