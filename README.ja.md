# Agent Session Control Stack

長時間動作する AI コーディングエージェントのための参照アーキテクチャ。

English: [README.md](README.md)

## Problem

長時間の AI コーディングエージェントは、決まったパターンで劣化します。

- コンテキストの肥大
- cache 再読込の浪費
- compact による状態喪失
- 失敗したアプローチの反復
- plan / worker 構成の消失
- 要約後の危険な再開（要約を事実と誤認する）

## Thesis

これを 1 つの問題として扱わず、4 つの層に分離します。

1. **Compression（圧縮）** — 肥大した入力コンテキストを圧縮する
2. **Health Detection（健全性検知）** — セッションの過熱を検知し、モデル自身を介して介入する
3. **Checkpointing（状態保存）** — 文脈が失われる前に plan・決定・失敗試行・worker 構成を保存する
4. **Recovery（復旧）** — 安全に再開する: *要約は仮説、原本が真実*

層の契約は独立しており、単体で導入・撤去できます（binding 上の注意が 1 点: Claude Code では Checkpoint と Recovery は同一 plugin（compact-plus）で提供されるため、対で導入・撤去されます）。

## Existing projects

- [pxpipe](https://github.com/teamchong/pxpipe)（teamchong）: 圧縮層
- [claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health)（House-lovers7）: 健全性検知層
- [compact-plus](https://github.com/u-ichi/compact-plus)（u-ichi）: 状態保存・復旧層

本リポジトリはこれらを**置き換えません**。コードも同梱しません。安全な組み合わせ方を文書化するものです。

## Claude Code reference stack

> - 畳み時の判定は **session-health** に任せる。
> - compact 前後の状態保存・復元は **compact-plus** に任せる。
> - 肥大した入力の圧縮は **pxpipe** に任せる。ただし byte-exact な値は決して圧縮しない。

合成を衝突させない 1 つのルール: session-health と compact-plus は、それぞれ異なる基準でモデルに compact を促せます。本 stack は **session-health を唯一の判定者**と定め、compact-plus の reminder を**設定ではなく構成で**無効化します。reminder は外部 statusline が warn marker ファイルを書いたときだけ発火するため、marker 生成器を導入しなければ一度も発火せず、state 保存・復旧注入は無傷で動き続けます。

- セットアップ・hook 責務・env 規約: [docs/claude-code/recommended-stack.md](docs/claude-code/recommended-stack.md)
- 設定スニペット: [examples/claude-code/settings.example.json](examples/claude-code/settings.example.json)

## Codex reference stack

Codex には compact lifecycle hook が無いため、本 stack はそれを模倣しません。同じ Checkpoint / Recovery の契約を **session handoff protocol** として実装します。`AGENTS.md` が「作業前に `.agent-session/handoff.md` と state ファイルを読む」「作業中に決定と失敗試行を記録する」「停止前に handoff を書く」を宣言します。checkpoint スナップショットは compact-plus の state file と同じ 10 セクションを使うため、handoff は runtime をまたげます。

これは hook より弱い保証（決定論的実行ではなく protocol 遵守）であり、そのことを明記しています。

- 設計: [docs/codex/adapter-design.md](docs/codex/adapter-design.md)
- そのまま使える protocol: [examples/codex/AGENTS.md](examples/codex/AGENTS.md)
- テンプレート: [templates/](templates/)

## Safety

pxpipe は最も強力で、最も注意が必要な層です。設計上 lossy であり、upstream 自身のテストで、dense image 内の 12 文字 hex 文字列の正読は Fable 5 で 13/15、Opus 4.8 で 0/15。誤読はエラーではなく **silent confabulation** になります。byte-exact な値（hash / ID / secret / path / migration 名 / deploy target）は text のまま残す必要があり、カテゴリ別の除外は現状 `npx` 経路では**設定できません**。実際に取れる制御は、byte-exact な作業を allowlist 外モデルへ逃がす運用です。

pxpipe を有効化する前に [docs/claude-code/pxpipe-safety.md](docs/claude-code/pxpipe-safety.md) を読んでください。

## Measurement

各 OSS には個別の実測があります（pxpipe: README 記載のスナップショットで請求ベース約 59〜70% 削減 / session-health: `/compact` でセッション内中央値 66% 削減、正規化 cacheRead/output 比 233x→83x — 作者自身が「因果ではなく整合性の証拠」と明記）。**3 つを併用したときの合算効果は未測定です。**

本リポジトリは、効果を主張する前に「効いている」の定義を先に固定します。指標・実験手順・明示的な撤退基準 — compact 後の迷走、却下案の再提案、同じ失敗の反復、1 成果物あたりのトークンコストが改善しなければ、この統合は複雑化に過ぎません。

- [docs/measurement-plan.md](docs/measurement-plan.md) · [docs/risk-register.md](docs/risk-register.md)（リスク・未検証点・撤退基準）

## Attribution

本リポジトリは統合・参照アーキテクチャであり、元のアイデアや実装の所有権を主張しません。クレジットの詳細は [ATTRIBUTION.md](ATTRIBUTION.md)。upstream 作者の方で記述の誤りを見つけた場合は issue を立ててください。訂正を最優先します。

## More

- 設計原本（Phase 0、日本語）: [architecture](docs/architecture.md) · [hook 責務分離](docs/hook-responsibilities.md) · [adapter interface](docs/adapter-interface.md) · [Codex AGENTS.md 案](docs/codex/agents-md-draft.md) · [implementation plan](docs/implementation-plan.md) · [acceptance criteria](docs/acceptance-criteria.md) · [risk register](docs/risk-register.md) · [measurement plan](docs/measurement-plan.md)
- Roadmap: Phase 0 設計 ✅ → Phase 1 docs-only 参照アーキテクチャ（本セット）→ Phase 2 実セッション before/after 測定 → Phase 3 upstream 協調 → Phase 4+ ツール化（generator / doctor / measurement、Phase 2 が撤退基準をクリアした場合のみ）
- License: MIT — [LICENSE](LICENSE)
