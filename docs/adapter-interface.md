# Adapter Interface — Claude Code / Codex 共通抽象

> Phase 0 設計原本。4 層を runtime 非依存のインターフェースとして定義し、各 runtime の binding（実装手段）を分離する。

## 1. 設計原則

- **層の契約は runtime に依存しない**。Claude Code の hook 名や Codex のファイル規約は binding の詳細であり、契約ではない
- **各層は独立に導入・撤去できる**。1 層だけ入れても意味があり、4 層すべてを要求しない
- **runtime固有実装をそのまま移植しない**。同じ契約を、各runtimeのnative hookとportableなstate protocolで満たす

## 2. 層ごとの契約

### Layer 1: Compression

```
契約:
  入力: モデルへ送るリクエスト（system prompt / tool docs / 履歴 / tool results）
  出力: 意味を保ちトークン数を減らしたリクエスト
  不変条件:
    - ユーザーの直近入力とモデル出力を変更しない
    - byte-exact values（hash / ID / secret / path / SHA）を lossy 変換に乗せない
    - いつでも無効化できる（kill switch）
```

### Layer 2: Health Detection

```
契約:
  入力: セッションの消費シグナル
  出力: ok / warn / hot の判定と、hot 時の介入
        （介入の様式 — エージェント自身への行動提案か、別の方式か — は binding の詳細。
          Claude Code binding は閉ループ提案方式を採る）
  不変条件:
    - 「畳む」判断を出すのはこの層だけ（single decider）
    - 介入は小さく・低頻度（注入トークン予算を守る）
    - 検知失敗がセッションをブロックしない（fail open）
```

### Layer 3: Checkpoint

```
契約:
  入力: 「まもなく文脈が失われる」トリガー（compact 前 / セッション終了前 / 危険操作前）
  出力: 再開に必要な最小状態の永続化
  状態スキーマ（10 セクション、compact-plus 由来）:
    Active Plan / Current Phase / TaskList Summary / Session Decisions /
    Constraints and Blockers / Worker Topology / Skills Invoked /
    Editing Files / Failed Attempts / Recovery Notes
  不変条件:
    - 原本（transcript / plan file）のバックアップと要約 state は別物として両方残す
```

### Layer 4: Recovery

```
契約:
  入力: 文脈喪失後の最初の再開点（compact 直後の初プロンプト / 新セッション開始）
  出力: state への参照注入と、認識規律の再宣言
  不変条件:
    - "summary is hypothesis, source is truth"
      （要約・compact summary は仮説。原ファイル・state・plan が正）
    - 復旧注入は 1 回で消費される（毎プロンプトに居座らない）
```

## 3. Binding マトリクス

| 層 | Claude Code binding | Codex binding |
|---|---|---|
| Compression | pxpipe（local proxy、`ANTHROPIC_BASE_URL` 差し替え） | **移植しない（Phase 0 判断）**。CLI 接続・API 形式・tool 定義の扱いが未検証。思想（bulky context を主文脈に入れない）のみ AGENTS.md の運用規律として反映 |
| Health | session-health（UserPromptSubmit hook + transcript scan） | 代理シグナル + 自己申告。session-health が測る指標面に相当するものは未検証（risk-register 参照）のため、経過時間 / tool call 数 / diff 量 / テスト失敗回数 / prompt 数を根拠に、AGENTS.md が checkpoint 更新をトリガーする。wrapper（`codex-session run` による自動監視）は Phase 2+ |
| Checkpoint | compact-plus（PreCompact hook、自動） | `PreCompact(manual\|auto)`で内容最小のboundary receiptを自動記録し、state本文はAGENTS.md protocolで更新 |
| Recovery | compact-plus（PostCompact marker → UserPromptSubmit 注入、自動） | `PostCompact`でreceiptを閉じ、`SessionStart(source=compact)`で同一sessionに1回だけrecovery guardを追加。hook無効時はhandoff.mdへfallback |

## 4. binding 間の本質的差分

| 観点 | Claude Code | Codex |
|---|---|---|
| lifecycle event | あり（PreCompact / PostCompact / UserPromptSubmit） | あり（PreCompact / PostCompact / SessionStart source=compact） |
| 実行主体 | hook（決定論的、エージェントの意思に依存しない） | boundaryはhook、state本文更新はAGENTS.md protocol |
| 状態の置き場 | plugin 管理（`${TMPDIR}` / `~/.claude/backups/`） | repo 内 `.agent-session/`（git 管理外推奨、可視・可編集） |
| 保証水準 | 強（reviewed pluginとruntime dispatchが前提） | 中（boundary検知はnative hook、state完全性はprotocol adherenceを測定） |

Codex native hookはcompact境界を決定論的に捉えるが、plan・decision・failed attemptの内容生成までは保証しない。project trust、hook definitionのreview、managed policyでhookが無効になり得るため、manual handoff fallbackも残す。

また、契約としての 4 層は独立だが、Claude Code binding では Checkpoint と Recovery を同一 plugin（compact-plus）が実装するため、binding レベルではこの 2 層は対で導入・撤去される。

## 5. 拡張の置き場所

- 新しい runtime（Cursor / 自作 agent 等）を足す場合: §2 の契約を満たす binding を 1 列追加する。契約側は変更しない
- 新しいツールで既存層を差し替える場合（例: 別の圧縮 proxy）: 層の不変条件を満たすことを確認し、binding マトリクスの 1 セルだけ入れ替える
