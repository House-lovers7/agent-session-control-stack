# ASCS ユーザーガイド

「これは何？」から、スタックを動かして診断結果を読めるようになるまでを 1 本にまとめたガイドです。正典ドキュメントを置き換えるものではなく、要約とリンクで導線をつくります。

English: [user-guide.md](user-guide.md)

## 1. これは何？（1 分で）

長時間動く AI コーディングエージェントのセッションは、決まったパターンで劣化します。コンテキストが肥大し、セッションが「過熱」し、compact が作業状態を捨て、エージェントは要約を事実と誤認したまま再開します。

Agent Session Control Stack（ASCS）は、この問題を 4 つの関心事に分け、既存 OSS 3 つを組み合わせる **reference 構成**です:

| 層 | 何の処理をするか | ツール（作者） |
|---|---|---|
| 1. Compression（圧縮） | リクエスト経路上で肥大した入力コンテキストを圧縮する（任意・オプトイン） | [pxpipe](https://github.com/teamchong/pxpipe)（teamchong） |
| 2. Health Detection（健全性検知） | セッションの過熱を検知し、compact を助言する | [claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health)（House-lovers7） |
| 3. Checkpointing（状態保存） | compact の前に transcript と作業状態を保存する | [compact-plus](https://github.com/u-ichi/compact-plus)（u-ichi） |
| 4. Recovery（復旧） | compact の後に保存した状態を再注入し、安全に再開させる | compact-plus（層 3 と同一プラグイン） |

全体を貫く核となるルール:

> **要約とstateは未信頼の仮説。現在の原本とfreshな検証結果が真実。**

このリポジトリが**でない**もの: ベンチマークではありません。upstream のコードを同梱・改変しません（プラグインは各作者の原本リポジトリを参照インストールします — [ATTRIBUTION.md](../ATTRIBUTION.md)）。生産性向上や速度改善も**主張しません**。3 つを併用したときの合成効果は**まだ実証されていません** — [Evidence status](../README.ja.md#evidence-status) を参照してください。

## 2. 仕組み: それぞれが実際に何をしているか

### Hook の発火面（Claude Code）

各ツールはセッションライフサイクルの異なる地点に触れるため、互いに踏み合いません:

| いつ | 誰が | 何が起きるか |
|---|---|---|
| 毎リクエスト（proxy、任意） | pxpipe | 肥大したコンテンツをモデルに届く前に画像へ書き換える |
| 過熱中にプロンプトを送信したとき | session-health | `/compact` を促す約 60 トークンの警告を注入する（最大 20 リクエストに 1 回） |
| compact の直前（`PreCompact`） | compact-plus | transcript をバックアップし、任意で 10 セクションの state ファイルを書く |
| compact の直後（`PostCompact` + 次のプロンプト） | compact-plus | recovery marker を置き、次のプロンプトに 1 回だけ復旧ノートを注入する |

### single compact decider（唯一の compact 判定者）ルール

session-health と compact-plus は、どちらも異なる基準でモデルに compact を促せます。「今すぐ compact」という声が 2 つあると挙動が不安定になるため、本 stack は **session-health を唯一の判定者**と定めます。compact-plus の reminder は**設定ではなく構成で**オフになります: reminder は外部の statusline スクリプトが warn marker ファイルを書いたときだけ発火しますが、本 stack はその生成器をそもそも導入しません。compact-plus の状態保存と復旧は無傷で動き続けます。

このルールは `/ascs:doctor` が検査します（第 4 節）。詳細な根拠: [recommended-stack.md](claude-code/recommended-stack.md)。

## 3. クイックスタート（Claude Code、約 5 分）

### プラグインをインストールする

```bash
claude plugin marketplace add House-lovers7/agent-session-control-stack
claude plugin install session-health@ascs   # 層 2: 健全性検知
claude plugin install compact-plus@ascs     # 層 3+4: 状態保存 + 復旧
claude plugin install ascs@ascs             # /ascs:doctor（read-only 診断）
```

### 有料 API 呼び出しを発生させない設定にする

compact-plus のデフォルトの state ファイル生成は `claude -p …` を実行します — **compact のたびに有料 API 呼び出し**が発生します。推奨設定は両方の backend を空文字列にし、state ファイル生成を明示的なオプトインにします:

```json
{ "env": { "COMPACT_PLUS_PRIMARY_BACKEND": "", "COMPACT_PLUS_FALLBACK_BACKEND": "" } }
```

そのまま使えるスニペット: [settings.example.json](../examples/claude-code/settings.example.json)。両 backend が空でも transcript バックアップと復旧注入は動きます — LLM 生成の state ファイルが無くなるだけです。同じ 10 セクションで手動チェックポイントを取るには [templates/state-file.md](../templates/state-file.md) を使ってください。

### 確認する

Claude Code 内で:

```text
/ascs:doctor
```

各層の状態と single-decider チェックを報告します。read-only です: 何もインストールせず、何も起動せず、API を呼ばず、設定も変更しません。

### 任意: pxpipe を有効化する（先に safety notes を読むこと）

pxpipe はプラグインではなくリクエスト経路の proxy で、**設計上 lossy** です — 誤読はエラーにならず silent confabulation になります。byte-exact な作業（commit SHA、ID、secret、正確なパス、migration 名、deploy target）は決して通さないでください。有効化前に [pxpipe-safety.md](claude-code/pxpipe-safety.md) を読んでください。

```bash
npx -y pxpipe-proxy@0.8.0              # レビュー済み version — 127.0.0.1:47821 で proxy 起動
alias claude-px='ANTHROPIC_BASE_URL=http://127.0.0.1:47821 claude'
```

`settings.json` にグローバルな `ANTHROPIC_BASE_URL` を書かず、alias によるオプトインにしてください — proxy が起動していないのに設定だけ残っていると、全リクエストが失敗します（トラブルシューティング参照）。

## 4. 日常の使い方

### スタックが有効なセッションで何が起きるか

1. 普段どおり作業します。健全なセッションでは、このスタックの注入は **0 トークン**です。
2. セッションが過熱します（長い transcript、悪化した cacheRead/output 比）。session-health が `/compact` を促す短い警告を注入します。
3. あなた（またはモデル）が `/compact` を実行します。compact の前に compact-plus が transcript をバックアップし、backend にオプトインしていれば 10 セクションの state ファイルを書きます。
4. compact の後、次のプロンプトに、保存された状態を指す復旧ノートが 1 回だけ注入されます。
5. 再開します — compact の要約**と**保存された state はどちらも仮説として扱い、現在の原本と fresh なコマンド出力で検証します（[state-trust-contract.md](state-trust-contract.md)）。

### `/ascs:doctor` の出力の読み方

```text
  1 Compression   pxpipe proxy: not listening on 127.0.0.1:47821 (layer inactive — optional, opt-in)
  2 Health        session-health plugin: INSTALLED (single compact decider)
  3 Checkpoint    compact-plus plugin: INSTALLED (transcript backup + state capture on PreCompact)
  4 Recovery      compact-plus plugin: INSTALLED (recovery injection after compaction)

  Single-decider rule: OK (no compact-warn marker producer detected; ...)
```

- **「not installed」「not listening」は情報表示であってエラーではありません** — 各層は単体で導入・撤去できます。
- Exit code `0` = 衝突なし。`1` = single-decider の **CONFLICT**（compact-warn marker の生成器が有効で、2 つのコンポーネントが compact を助言している状態 — 生成器を撤去してください）。
- pxpipe が listen 中なら、doctor は**このセッション**が実際に proxy を経由しているか（`ANTHROPIC_BASE_URL`）も教えてくれます。

## 5. Codex で使う

Codex には compaction hook が無いため、層 3+4 はプラグイン自動化ではなく **handoff protocol** になります — hook より弱い保証（決定論的実行ではなく protocol 遵守）であり、そのことを明記しています。

1. [examples/codex/AGENTS.md](../examples/codex/AGENTS.md) をプロジェクトにコピーまたは適応します。
2. `.agent-session/` ディレクトリを作ります。
3. protocol により、エージェントは作業前に `handoff.md` と state ファイルを読み、作業中に決定と失敗試行を記録し、停止前に handoff を書きます。

前セッションが残した live state を読む前に、read-only 検査を実行してください — `.agent-session/` は未信頼の復旧 context であり、指示チャネルではありません:

```bash
python3 scripts/check_state.py --repo /path/to/consumer-repo
```

Exit `0` = 合格（または state なし）、`2` = 陳腐化（使う前に再構築）、`1` = 不正または unsafe（無視する）。権限境界の全文は [state-trust-contract.md](state-trust-contract.md) を参照してください。

state ファイルは compact-plus と同じ 10 セクションを使うため、handoff は runtime をまたげます。設計の詳細: [codex/adapter-design.md](codex/adapter-design.md)。

## 6. 信じる代わりに測る: `scripts/ascs.py`

記録された evidence が何を支持し、何を支持しないかを報告する measurement ヘルパーが同梱されています:

```bash
python3 scripts/ascs.py doctor                    # repo 形状の準備チェック
python3 scripts/ascs.py measure --experiment 004  # read-only の claim-boundary レポート
```

`measure` は evidence を保守的に分類し（stopped / void / not-run）、生産性向上の主張は決してしません。コマンドの全リファレンス（`init` / `record` / `finish` / `score`）: [measurement-harness.md](measurement-harness.md)、判定ルール: [claim-boundary-model.md](claim-boundary-model.md)。

## 7. トラブルシューティングと FAQ

**`/ascs:doctor` が CONFLICT を報告する。** statusline または hook が compact-warn marker ファイルを書いており、session-health と compact-plus の両方が compact を助言する状態です。marker 生成器を撤去してください（`~/.claude/settings.json` 内の `claude-compact-warn` 参照を確認）。

**pxpipe を有効化した直後から全リクエストが失敗する。** `ANTHROPIC_BASE_URL` が proxy を向いているのに、何も listen していない状態です。proxy を起動する（`npx -y pxpipe-proxy@0.8.0`）か、変数を unset してください。予防策: `settings.json` ではなくオプトインの alias を使うこと。その他のケース（再起動後に proxy が消える、`PXPIPE_DISABLE=1` での一時バイパス）: [recommended-stack.md → Troubleshooting](claude-code/recommended-stack.md#troubleshooting-pxpipe)。

**compact 後に state ファイルが生成されない。** 推奨（無料）設定では期待どおりの挙動です — 両 backend が空のためです。transcript バックアップは残っています。backend にオプトインするか、手動の [state-file.md](../templates/state-file.md) チェックポイントを使ってください。

**このスタックの実行にお金はかかる？** 推奨設定では、かかりません: session-health と doctor はローカルで動き、compact-plus の有料 backend は無効化されています。唯一の有料経路は、LLM による state ファイル生成へのオプトインです。

**セッションは速く・安くなる？** 不明です。upstream 各プロジェクトは独自の実測を公表していますが、合成効果は未検証です — このリポジトリは [measurement](measurement-plan.md) が裏づけるまで、その主張を意図的に拒否します。

**常に使うべき？** いいえ。小さな作業、byte-exact な作業、別の承認ゲートがない workflow では、まず [when-not-to-use.md](when-not-to-use.md) を読んでください。

## 8. 次に読むもの

| 目的 | 読むもの |
|---|---|
| セットアップ順序・hook 責務・env 規約（正典） | [claude-code/recommended-stack.md](claude-code/recommended-stack.md) |
| pxpipe 有効化前のリスク境界 | [claude-code/pxpipe-safety.md](claude-code/pxpipe-safety.md) |
| `.agent-session/` の state をどこまで信頼するか | [state-trust-contract.md](state-trust-contract.md) |
| なぜ 4 層か・設計根拠 | [architecture.md](architecture.md) |
| エンドツーエンドの動くデモ | [claude-code-reference-integration.md](claude-code-reference-integration.md) · [examples/claude-code/stack-demo/](../examples/claude-code/stack-demo/) |
| 実セッションのケーススタディ | [case-study-dogfood-0.2.md](case-study-dogfood-0.2.md) |
| どんな evidence が存在する（しない）か | [README → Evidence status](../README.ja.md#evidence-status) · [claim-boundary-model.md](claim-boundary-model.md) |
| 導入し**ない**ほうがよい理由 | [when-not-to-use.md](when-not-to-use.md) |
| upstream クレジット | [ATTRIBUTION.md](../ATTRIBUTION.md) |
