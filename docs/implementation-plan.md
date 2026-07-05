# Implementation Plan — フェーズ分割と分担

> Phase 0 設計原本。実装は行わず、各フェーズの成果物・担当・停止条件を定義する。

## 0. 分担原則

```
Fable（設計担当）:
  責務分離 / 共通抽象 / hook 設計と競合回避 / Codex protocol 設計 /
  リスク・撤退基準・検証指標 / フェーズ分割 / 設計レビュー

Codex（実装担当）:
  公開用ドキュメント整形（英語 README 等）/ examples・templates の実体化 /
  ファイル配置 / script 実装（Phase 2+）/ lint・修正ループ
```

## Phase 0: 設計（完了 — 本ドキュメント群）

成果物: docs/architecture.md / hook-responsibilities.md / adapter-interface.md / codex/agents-md-draft.md / implementation-plan.md / acceptance-criteria.md / risk-register.md / measurement-plan.md + README（暫定）+ ATTRIBUTION.md + LICENSE

## Phase 1: Docs-only reference architecture（Codex 実装）

本設計を入力として、公開可能な最小構成に整形する。

### 目標ファイルレイアウト（initial public set）

```
agent-session-control-stack/
  README.md                # Problem → 4層 Thesis → Existing projects →
                           #   Claude Code stack → Codex stack → Safety →
                           #   Measurement → Roadmap → Attribution（英語）
  README.ja.md             # 同構成の日本語版
  ATTRIBUTION.md
  LICENSE
  docs/
    architecture.md                    # 本設計 §を英語公開版に整形
    claude-code/recommended-stack.md   # hook-responsibilities.md §3-4 +
                                       #   セットアップ手順 + pxpipe safety を統合
    codex/adapter-design.md            # agents-md-draft.md を公開版に整形
  examples/
    claude-code/settings.example.json  # hook-responsibilities.md §4 の env 規約
    codex/AGENTS.md                    # agents-md-draft.md §2 の protocol 実体
  templates/
    state-file.md                      # 10 セクションテンプレ
```

### Codex への指示の要点

- 事実関係は Phase 0 設計原本（docs/ 配下）を正とする。**新しい仕様主張を追加しない**（特に pxpipe の設定可能性、compact-plus の閾値挙動）
- トーン: 3 OSS への敬意。「置き換えない」を README 冒頭で宣言
- Claude Code 固有と Codex 汎用を必ず分けて書く

### 停止条件

- acceptance-criteria.md の Phase 1 基準を満たしたら止める。scripts / CLI / 自動化を追加しない

## Phase 2: 自リポジトリでの検証（Codex 実行、測定は measurement-plan.md）

- 実プロジェクト 1〜2 セッションで stack を運用し、compact 後の迷走・手戻り・復旧時間・却下案再提案を記録
- Codex 側: AGENTS.md protocol の遵守率（checkpoint 更新が実際に起きた回数 / トリガー該当回数）を記録
- 成果物: templates の experiment report 形式による測定ログ（Phase 4 で repo に追記）

## Phase 3: 設計レビューと発信準備（Fable）

- 設計の穴の総点検（測定結果を受けた契約・閾値の見直し）
- OSS 作者への共有文面（upstream 提案）と Zenn 記事構成の確定
- public 化・X・Zenn・作者への Issue/Discussion は **すべて external_send として個別承認**

## Phase 4 以降（ROADMAP、着手判断は Phase 2 の結果次第）

- Phase 4: Config generator（settings 例 / AGENTS.md / state templates の生成）
- Phase 5: Doctor script（3 ツールの導入状態と二重通知構成の検査）
- Phase 6: Measurement tool（before/after の自動集計）
- Phase 7: Upstream proposals（session-health / compact-plus への issue、pxpipe への safety doc 提案）

## 全フェーズ共通の撤退基準

measurement-plan.md の指標が改善しない場合、この統合は複雑化に過ぎない。risk-register.md の撤退基準に従い、Phase 4 以降へ進まない。
