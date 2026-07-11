# Risk Register — リスク・未検証点・撤退基準

> Phase 0 設計原本。過大評価を避けるため、リスクと限界を先に固定する。

## 1. リスク一覧

| # | リスク | 影響 | 確度・根拠 | 緩和策 |
|---|---|---|---|---|
| R1 | **pxpipe の silent confabulation**: 画像化された hex / ID / 名前をモデルが自信を持って誤読する（12 文字 hex 正読: Fable 5 13/15、Opus 0/15。README に人名誤想起の実害例あり） | 高（誤った ID での操作・誤情報の混入。エラーにならないため検出困難） | [高] README 明記 | byte-exact 作業は allowlist 外モデルの subagent へ逃がす。破壊的操作・deploy・migration を含むセッションでは `PXPIPE_DISABLE=1`。事故 1 件で当該ワークフローから pxpipe を外す |
| R2 | **transcript 内部仕様への依存**: session-health（`compact_boundary`、`subagents/` レイアウト）と compact-plus（JSONL 形状）は Claude Code の未文書仕様に依存。本体更新で静かに壊れうる | 中（検知・checkpoint が無言で機能停止） | [高] session-health README が自認 | 両ツールとも fail open 設計のためセッションは壊れない。定期的に発火実績を確認（Phase 5 doctor script の動機） |
| R3 | **compact-plus の LLM バックエンド課金**: state file 生成が既定で `claude -p`（有料 API）を呼ぶ。compact のたびに発生 | 中（気づかない継続課金） | [高] hooks ソース確認済み | 初期構成は `COMPACT_PLUS_PRIMARY_BACKEND=""`（スキップ）。有効化は明示オプトインとし、examples にコスト注記 |
| R4 | **「畳め」指示の二重化**: compact-plus reminder と session-health が併走すると、基準の異なる 2 つの compact 提案がモデルに届く | 中（挙動の不安定化・注入の無駄） | [高] 双方の hook 実装確認済み | warn-marker 生成器を導入しない（構成的 off、hook-responsibilities.md §3） |
| R5 | **Codex protocol の不遵守**: Codex binding は hook でなくエージェントの AGENTS.md 遵守に依存する。checkpoint を書かずに突き進む可能性 | 中（Codex 側だけ保全が効かない） | [中] 一般にモデルの指示遵守は確率的 | Phase 2 で遵守率を測定。低ければ Skills 化 → wrapper（Phase 2+）で強制点を作る |
| R6 | **pxpipe × compact-plus の相互作用が未測定**: transcript はローカルで原文のまま書かれるため backup / state 生成への影響は無いはず、という推定に留まる | 低〜中 | [中] pxpipe が触るのは送信リクエストのみ、という仕様からの推定 | Phase 2 で併用セッションを最低 1 本含め、state file の品質を目視確認 |
| R7 | **PostCompact hook の挙動詳細が未確認**: compact-plus の recovery は PostCompact の発火に依存。発火条件の細部（auto compact 時等）は plugin 資料からは未確認 | 低 | [中] | Phase 2 で auto / manual compact 両方の recovery 発火を確認 |
| R8 | **既存 OSS の更新で本 repo の記述が陳腐化**: meta-repo の宿命 | 低（誤案内） | [高] 構造的に必然 | 2026-07-10確認のimmutable version/SHA/integrityを `config/upstreams.lock.json` に固定。lock・marketplace・運用コマンドの一致をCIで必須化し、更新はHuman Approval Gateを通す |

## 2. 未検証点（明示）

1. **Codex CLI に pxpipe 相当を安全に挟めるか** — pxpipe-proxy 0.8.0 が OpenAI Responses transport を実装することはsource確認済みだが、Codex CLIの接続経路・認証・tool挙動・byte-exact safetyのend-to-end互換性は未検証。transport実装の存在だけでstable対応とは扱わず、Compression層をCodex stable bindingへ移植しない
2. **Codex で Claude Code 並みの Checkpoint/Recovery がどこまで再現できるか** — protocol 遵守率は測定するまで不明
3. **3 層併用の相乗効果** — 各ツールの個別実測（pxpipe: 請求 59〜70% 減、session-health: compact でセッション内中央値 66% 削減・正規化比 233x→83x — いずれも作者が因果ではなく整合性の証拠と明記）はあるが、**併用時の合算効果・干渉は未測定**
4. **使用量上限（使用率表示）への効果** — 上限の算定は入力トークンだけで決まるとは限らない。「pxpipe で 70% 削減 = 使用率も 70% 改善」とは言えない
5. **`COMPACT_WARN_THRESHOLD` の境界挙動**（0 / 100 / 空） — marker 生成器が外部にあるため plugin 単体では検証不能（本 stack では生成器を入れないので実害なし）
6. **Codex のセッションログが Health 層の指標面になり得るか** — Codex CLI はセッション記録を永続化するが、session-health が測る cacheRead/output 相当の usage 情報を取り出せるかは未確認。確認できれば Codex binding の Health 層を代理シグナルから実測に格上げできる

## 3. 撤退基準

Phase 2 の測定（measurement-plan.md）で、以下のいずれも改善しない場合、**統合は複雑化に過ぎない**と判定し、Phase 4 以降（generator / doctor / measurement tool）へ進まない:

- compact 後の迷走回数（誤った前提での作業着手）
- 却下済み案の再提案回数
- 同じ失敗の再実行回数
- cacheRead/output 比（正規化系列）
- 1 成果物あたりの使用量（トークン / コスト）
- 作業再開時の手戻り時間

部分撤退の単位は層である（4 層は独立に撤去可能）。例: R1 事故が出れば Compression 層のみ外す。Health / Checkpoint / Recovery は影響を受けない。

## 4. このリポジトリ自体が主張しないこと

- 3 OSS の代替・上位互換であること
- 因果効果の証明（n 小・無統制。整合性の証拠まで）
- Claude Code / Codex の内部仕様の安定性
