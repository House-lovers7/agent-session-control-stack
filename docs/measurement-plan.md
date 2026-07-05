# Before/After Measurement Plan

> Phase 0 設計原本。Phase 2 検証で「効いているか」を判定するための指標・手順・判定規律。

## 1. 指標

### 一次指標（撤退基準に直結）

| 指標 | 定義 | 測定手段 |
|---|---|---|
| compact 後の迷走 | compact 直後の再開で、要約のみに基づく誤った前提で作業着手した回数 / compact 回数 | セッションログの目視判定（判定基準を experiment report に事前記載） |
| 却下案の再提案 | decision-log / 会話で一度却下された案が再提案された回数 | 同上 |
| 同一失敗の再実行 | failed-attempts 記載済みの失敗アプローチが再実行された回数 | 同上 |
| cacheRead/output 比 | セッション正規化系列（req≥10 のセッション中央値） | session-health の usage-report / 検証スクリプト |
| 1 成果物あたり使用量 | 完了タスク 1 件あたりの合計トークン・概算コスト | usage-report + pxpipe dashboard（127.0.0.1:47821、節約トークン表示） |
| 再開手戻り時間 | compact / 新セッション後、実質的な前進が再開するまでのプロンプト数 | ログ目視 |

### 二次指標（診断用）

- session-health の hot 到達率・hot 滞在時間、hook 発火回数
- compact-plus の state file 生成成否・recovery 注入の発火（marker 消費）確認
- pxpipe の圧縮リクエスト率・画像化バイト数（dashboard）
- Codex: checkpoint トリガー該当時の実施率（protocol 遵守率）

## 2. 実験設計

```
対象:    実プロジェクトの実タスク（合成タスクは使わない）
baseline: stack なし 1〜2 セッション（同種のタスク規模）
treated:  stack あり 1〜2 セッション
  Claude Code: session-health + compact-plus（backend "" / reminder 構成的off）
               + pxpipe（byte-exact 作業を含む場合は subagent 逃がしを併用）
  Codex:      AGENTS.md protocol + .agent-session/
記録:    experiment report（templates/、1 セッション 1 ファイル）に
         開始時に判定基準を書いてから作業する（事後基準変更を防ぐ）
```

### 統制上の注意

- タスク種・規模を揃える努力はするが、n=数セッションで統制は不可能。**得られるのは因果ではなく整合性の証拠**（session-health 作者の検証と同じ規律）
- 当日進行中セッションのデータは確定値にしない（bucket が閉じてから評価）
- pxpipe の A/B は `PXPIPE_DISABLE=1`（無再起動パススルー、メトリクス記録は継続）を使うと同一セッション内でも切替可能

## 3. Experiment report 最小スキーマ（templates 化する）

```
- date / runtime (claude-code | codex) / stack config（有効層と env）
- task summary / 完了定義
- 一次指標の実測値（上表の 6 つ）
- 二次指標（該当分）
- 事故記録: silent confabulation の有無（byte-exact 値の誤読）、
  hook 不発、state file 欠損
- 所感 1〜3 行（数値にならない違和感）
```

## 4. 判定

- 一次指標のいずれかが baseline 比で明確に改善 → 該当層を維持、Phase 4 検討
- いずれも改善なし → risk-register §3 の撤退基準を適用
- R1 事故（confabulation）が 1 件でも発生 → 当該ワークフローから Compression 層を外す（他層は継続）

## 5. 使わない指標（誤解防止）

- 使用率表示（rate limit 残量）の変化 — 算定方法が非公開で、入力削減と比例する保証がない
- 「体感の速さ」単独 — 必ず一次指標とセットで記録する
