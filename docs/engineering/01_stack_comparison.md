<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 技術スタック比較

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 観測された採用スタック

明示的なアプリケーションmanifestなし

## Package / workspace

| Package | Manifest |
|---|---|
| package manifest未検出 | - |

## トレードオフ

| 対象 | 現在 | 比較候補 | 現在案の利点 | 注意点 |
|---|---|---|---|---|
| 資産形態 | 現在のファイル構成 | runtime新設 | 移行を伴わず正典を保持 | 実行manifestがないため技術比較は未成立 |

> [中] 比較候補は現行実装を理解するための対照であり、移行提案ではない。当時の採用理由は既存ADRがあればそちらを正典とする。

## 判断を更新する条件

- manifest: 未検出
- quality config: `.github/workflows/test.yml`
- framework更新時はlockfile、build、typecheck、主要test、runtime smokeを同じ変更で確認する。
