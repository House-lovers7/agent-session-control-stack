<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — One Pager / オンボーディング概要

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## コンセプト

長時間AIコーディングエージェント運用の参照アーキテクチャmeta-repo。pxpipe/session-health/compact-plusを置き換えずCompression/Health/Checkpoint/Recoveryの4層に責務分離し、Claude Codeはhooks/plugin、CodexはAGENTS.md+state+handoff protocolで実装する設計を文書化。コード非同梱・docs-only。

## 誰の何を解くか

- 対象領域: AI/エージェント基盤
- 想定利用者: Claude Code/Codexヘビーユーザー / AIエージェント導入企業
- 価値仮説: 4層参照アーキテクチャ: compact提案の意思決定をsession-healthに一元化（compact-plusのwarn-marker生成器を導入しない構成的off）+ pxpipe lossy境界（byte-exact値はtext維持）+ 10セクションstate/checkpoint/handoff protocol

## 現在地

| 項目 | 観測結果 |
|---|---|
| 技術スタック | manifestから未特定 |
| API | 0 endpoint signal |
| データモデル | 1 unique entity signal |
| 画面 | 0 route/screen signal |
| 実行基盤 | config (`.github/workflows/test.yml`) |
| package / module | 1 component signal |
| tests | 8 file signal |

## ソースマップ

| Component | Path | 責務 |
|---|---|---|
| `scripts` | `scripts` | CLI・バッチ・運用入口 |

## 最初に使うコマンド

| 目的 | Command |
|---|---|
| 未検出 | READMEまたはCIから確認 |

## 変更箇所の入口

| 変更対象 | 最初に読むpath | 同時に確認するもの |
|---|---|---|
| データモデル | `scripts/exp004.py` | migration、制約、seed、API型 |
| 実行・配備 | `.github/workflows/test.yml` | 環境変数、service依存、rollback |
| 回帰検査 | `tests/test_exp004.py` | 変更対象に近いtestと全体check |

## 引継ぎ時の未解決ギャップ

| Priority | Requirement | 状態・理由 | Evidence |
|---|---|---|---|
| P1 | `entrypoints` | missing: 実行entrypointを特定できない。資料/資産なら「実行物なし」の明記が必要。 | `docs/engineering/README.md` |
| P1 | `major_modules_and_packages` | partial: package/moduleはあるが、責務、依存方向、公開境界、影響範囲が不足。 | `config/` |
| P1 | `observability` | missing: 可観測性の実装証拠を特定できない。生成文書の一般要件・提案は現行実装の証拠ではない。 | `ATTRIBUTION.md` |
| P1 | `startup_and_verification_commands` | missing: 起動・検証commandを静的証拠から特定できず、生成文書にも実行可能な手順がない。 | `README.md` |

## スコープ境界

- [高] productionの稼働、外部provider設定、secret値は未確認。
- [高] API・DB・画面が未検出の場合は推測せず、実装入口の追加を課題として残す。
- [中] 初回変更前に `07_traceability.md` の根拠と未確認事項を確認する。
