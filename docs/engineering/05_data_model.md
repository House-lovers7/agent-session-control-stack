<!-- generated-by: scripts/generate_engineering_docs.py -->
# Agent Session Control Stack — データ契約

> 2026-07-16に実装と正典文書を再確認。ASCSは永続DBやERモデルを持たない。

## Local artifact model

| Artifact | Format | Owner | Trust boundary |
|---|---|---|---|
| session state | Markdown + metadata envelope | `.agent-session/` | 未信頼。repo/branch/commit/session/expiryを検査 |
| compact receipt | JSON | Codex native hook | transcript本文・pathを保存しない。same-session one-shot |
| experiment events | JSONL | `scripts/ascs.py`, experiment helpers | schema/version/duplicate/pair transactionをfail-closed検査 |
| experiment report | Markdown | measurement harness | observed/allowed/disallowed claimを分離 |
| upstream lock | JSON | `config/upstreams.lock.json` | immutable revisionとreviewed contentを検証 |

## Invariants

- stateは承認・権限・secret storeではない。
- frozen experiment evidenceをproduct code更新で書き換えない。
- malformed、unknown version、partial pair transactionから比較claimを作らない。
- receiptはtranscript contentやmachine-specific pathを永続化しない。

正典: `docs/state-trust-contract.md`、`docs/claim-boundary-model.md`、
`docs/codex/adapter-design.md`。
