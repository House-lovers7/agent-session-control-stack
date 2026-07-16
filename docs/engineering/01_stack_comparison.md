<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 技術スタック比較

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 観測された採用スタック

依存package manifestを持たず、Python標準ライブラリ中心のCLI・hook・検証scriptとして構成する。

## Package / workspace

| Package | Manifest |
|---|---|
| Python CLI / hooks | `scripts/`, `plugins/ascs/scripts/`, `examples/codex/.codex/hooks/` |

## トレードオフ

| 対象 | 現在 | 比較候補 | 現在案の利点 | 注意点 |
|---|---|---|---|---|
| 依存管理 | stdlib中心・package manifestなし | package化 | install不要で監査しやすい | copy/merge手順とPython互換性をCIで維持する必要 |

> [中] 比較候補は現行実装を理解するための対照であり、移行提案ではない。当時の採用理由は既存ADRがあればそちらを正典とする。

## 判断を更新する条件

- dependency manifest: 意図的に不使用
- quality config: `.github/workflows/test.yml`
- framework更新時はlockfile、build、typecheck、主要test、runtime smokeを同じ変更で確認する。
