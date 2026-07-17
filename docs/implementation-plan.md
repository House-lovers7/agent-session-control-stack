# Implementation Plan — フェーズ分割と分担

> Phase 0 設計原本 / **内部の作業計画メモ**（authoring workflow）。公開ドキュメントの正典は README と docs/claude-code/・docs/codex/。本書は当初計画と現在地を分離し、各フェーズの成果物・担当・停止条件を定義する。

## Current implementation status (2026-07-16)

- **Phase 1 reference architecture: implemented.** README、runtime別adapter、
  examples、templatesが公開可能な形で存在する。
- **Phase 2 measurement harness: implemented.** `scripts/ascs.py`の手動記録、
  scoring、claim-boundary measurementとExperiment 002–004の履歴がある。
- **Install-state Doctor: implemented early as a safety diagnostic.** 効果実証後の
  製品化としてではなく、二重compact提案・routing不備・設定ドリフトを実験前に
  検出する安全ゲートとして先行実装した。
- **Synthetic compact-plus recovery smoke: implemented.** content-attestedな
  PostCompact markerと次promptの1回注入を隔離manual/auto入力で検査する。
  Claude runtime dispatch、PreCompact、効果は未検証のまま分離する。
- **Codex native compact-hook reference: implemented locally.** 2026-07-16の
  公式Hooks仕様へ追従し、PreCompact/PostCompact receiptと
  SessionStart(source=compact)のone-shot recovery guardを追加した。
  AGENTS.md protocolはstate本文更新とhook無効時のfallbackとして残す。
- **Synthetic Codex compact-hook smoke: implemented.** checked-in hookを
  subprocessとして合成manual/auto入力で実行し、trigger receipt、one-shot、
  機密値非保存を検査する。Codex/model/APIと実runtime dispatchは含まない。
- **Automated benefit measurement: not implemented.** transcript自動収集、
  dashboard、因果推定、無人before/after集計は提供しない。
- **Full-stack composition benefit: unvalidated.** mechanismの同時発火はdogfoodで
  確認済みだが、生産性・速度・費用・品質の改善効果は有効な比較実験を得るまで
  未実証として扱う。

この先行実装は、当初のPhase 4–6を完了扱いにする例外ではない。Evidenceを安全に
集め、過大claimを拒否するためのread-only Doctorとmeasurement helperだけを
Phase 2へ前倒しした。Config generator、automated benefit measurement、外部提案は、
Phase 2の撤退基準をクリアするまで着手判断を保留する。

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
- Codex 側: native hook発火率、one-shot receipt消費率、AGENTS.md protocolによるcheckpoint本文更新率を分けて記録
- 成果物: templates の experiment report 形式による測定ログ（Phase 4 で repo に追記）

## Phase 3: 設計レビューと発信準備（Fable）

- 設計の穴の総点検（測定結果を受けた契約・閾値の見直し）
- OSS 作者への共有文面（upstream 提案）と解説記事構成の確定
- 公開・SNS 投稿・作者への Issue/Discussion などの対外コミュニケーションは、**すべて人間の明示承認を経てから実行する**

## Phase 4 以降（ROADMAP、着手判断は Phase 2 の結果次第）

- Phase 4: Config generator（settings 例 / AGENTS.md / state templates の生成）
- Phase 5: Doctor productization（read-only safety diagnosticはPhase 2へ前倒し済み）
- Phase 6: Automated benefit measurement（保守的な手動集計helperはPhase 2へ前倒し済み）
- Phase 7: Upstream proposals（session-health / compact-plus への issue、pxpipe への safety doc 提案）

## 全フェーズ共通の撤退基準

measurement-plan.md の指標が改善しない場合、この統合は複雑化に過ぎない。risk-register.md の撤退基準に従い、Phase 4 以降へ進まない。
