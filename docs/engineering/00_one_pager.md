<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — One Pager / オンボーディング概要

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## コンセプト

長時間AIコーディングエージェント運用のreference stack。pxpipe/session-health/compact-plusを置き換えず4層に責務分離し、Claude Codeはupstream plugins、Codexはnative compact hooks + AGENTS.md + state protocolで実装する。read-only Doctor、state検査、measurement helper、hook referenceを含む。

## 誰の何を解くか

- 対象領域: AI/エージェント基盤
- 想定利用者: Claude Code/Codexヘビーユーザー / AIエージェント導入企業
- 価値仮説: 4層参照アーキテクチャ: compact提案の意思決定をsession-healthに一元化（compact-plusのwarn-marker生成器を導入しない構成的off）+ pxpipe lossy境界（byte-exact値はtext維持）+ 10セクションstate/checkpoint/handoff protocol

## 現在地

| 項目 | 観測結果 |
|---|---|
| 技術スタック | Python標準ライブラリ、shell、Claude/Codex hook設定、Markdown |
| API | 0 endpoint signal |
| データモデル | 永続DBなし。JSON/JSONL experiment evidenceとMarkdown state |
| 画面 | 0 route/screen signal |
| 実行基盤 | config (`.github/workflows/test.yml`) |
| package / module | CLI、Doctor、state checker、experiment helpers、Codex hook |
| tests | 9 files |

## ソースマップ

| Component | Path | 責務 |
|---|---|---|
| `scripts` | `scripts` | CLI・バッチ・運用入口 |

## 最初に使うコマンド

| 目的 | Command |
|---|---|
| test | `python3 -m unittest discover tests -v` |
| validation | `python3 scripts/validate_repo.py --require-upstream-lock` |
| repo doctor | `python3 scripts/ascs.py doctor` |

## 変更箇所の入口

| 変更対象 | 最初に読むpath | 同時に確認するもの |
|---|---|---|
| evidence schema | `scripts/ascs.py` | experiment profiles、claim boundary tests |
| 実行・配備 | `.github/workflows/test.yml` | 環境変数、service依存、rollback |
| 回帰検査 | `tests/test_exp004.py` | 変更対象に近いtestと全体check |

## 引継ぎ時の未解決ギャップ

| Priority | Requirement | 状態・理由 | Evidence |
|---|---|---|---|
| P1 | `codex_runtime_smoke` | focused testはPASS。実Codex manual/auto compact dispatchは未検証。 | `docs/codex/adapter-design.md` |
| P1 | `composition_efficacy` | 3層同時発火は確認済みだが便益比較は未成立。 | `README.md` |

## スコープ境界

- [高] productionの稼働、外部provider設定、secret値は未確認。
- [高] API・DB・画面が未検出の場合は推測せず、実装入口の追加を課題として残す。
- [中] 初回変更前に `07_traceability.md` の根拠と未確認事項を確認する。
