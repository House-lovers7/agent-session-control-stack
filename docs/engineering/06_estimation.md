<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — 見積り（オンボーディング・契約確認）

> 生成日: 2026-07-15 / 対象: `agent-session-control-stack` / 確度: [高]
> 実装・manifest・既存資料の静的棚卸しに基づく。外部サービスの稼働状態と本番構成は未検証。

## 前提

- 後発エンジニアが安全に最初の変更へ入るまでの確認作業を見積もる。
- 新機能実装、production変更、provider契約、データ移行そのものは含めない。
- P50/P90は静的に検出したAPI/entity/screen/test規模から算出した粗い時間幅。

| 作業 | P50 | P90 | 最初の根拠 | 完了条件 |
|---|---:|---:|---|---|
| ローカル再現 | 1h | 2h | README + CI | unitとrepo validationがPASS |
| runtime契約確認 | 2h | 4h | Claude/Codex adapter docs | hook trust、fallback、未検証境界を説明可能 |
| evidence契約確認 | 2h | 4h | `scripts/ascs.py` | claim boundaryと撤退基準を確認 |
| **合計** | **5h** | **10h** | - | 未確認事項をcloseまたはrisk accept |

> [低] 見積りは担当者の習熟度、依存サービス、fixture、実機、秘密情報の入手状況で変わる。最初の2時間でsetupを試し、失敗理由を反映して再見積りする。
