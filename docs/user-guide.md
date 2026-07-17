# ASCS User Guide

One document that takes you from "what is this?" to running the stack and reading its diagnosis. It summarizes and links to the canonical docs instead of replacing them.

日本語版: [user-guide.ja.md](user-guide.ja.md)

## 1. What is this? (one minute)

Long-running AI coding agent sessions fail in predictable ways: context bloats, the session "overheats", a compact throws away working state, and the agent resumes from a summary as if it were fact.

The Agent Session Control Stack (ASCS) is a **reference composition** of three existing OSS tools, one per concern:

| Layer | What it does | Tool (author) |
|---|---|---|
| 1. Compression | shrinks bulky input context on the request path (optional, opt-in) | [pxpipe](https://github.com/teamchong/pxpipe) (teamchong) |
| 2. Health Detection | notices when a session is getting hot and advises a compact | [claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health) (House-lovers7) |
| 3. Checkpointing | preserves transcript and working state before a compact | [compact-plus](https://github.com/u-ichi/compact-plus) (u-ichi) |
| 4. Recovery | re-injects that state after the compact so the session resumes safely | compact-plus (same plugin as layer 3) |

The core rule that ties them together:

> **Summary and state are untrusted hypotheses. Current source and fresh evidence are truth.**

What this repo is **not**: it is not a benchmark, it does not bundle or modify the upstream code (plugins install the authors' original repositories by reference — [ATTRIBUTION.md](../ATTRIBUTION.md)), and it does **not** claim productivity or speed gains. The effect of running all three together is **not empirically validated yet** — see [Evidence status](../README.md#evidence-status).

## 2. How it works: what each piece actually does

### Hook surfaces (Claude Code)

Each tool touches a different point in the session lifecycle, so they don't step on each other:

| When | Who | What happens |
|---|---|---|
| Every request (proxy, optional) | pxpipe | rewrites bulky content to images before it reaches the model |
| You submit a prompt while the session is hot | session-health | injects a ~60-token warning (at most once per 20 requests) suggesting a compact |
| Just before a compact (`PreCompact`) | compact-plus | backs up the transcript; optionally writes a 10-section state file |
| Just after a compact (`PostCompact` + next prompt) | compact-plus | drops a recovery marker, then injects a one-shot recovery note into your next prompt |

### The single-compact-decider rule

Both session-health and compact-plus *can* tell the model to compact, on different criteria — two "compact now" voices make behavior unstable. The stack designates **session-health as the only decider**. The compact-plus reminder stays off *by construction*: it only fires if an external statusline script writes a warn-marker file, and this stack simply never installs that producer. compact-plus's state capture and recovery keep working untouched.

`/ascs:doctor` checks this rule for you (section 4). Full rationale: [recommended-stack.md](claude-code/recommended-stack.md).

## 3. Quickstart (Claude Code, ~5 minutes)

### Install the plugins

```bash
claude plugin marketplace add House-lovers7/agent-session-control-stack
claude plugin install session-health@ascs   # layer 2: health detection
claude plugin install compact-plus@ascs     # layers 3+4: checkpoint + recovery
claude plugin install ascs@ascs             # /ascs:doctor (read-only diagnosis)
```

### Keep it free of paid API calls

compact-plus's default state-file generation runs `claude -p …` — **a paid API call on every compact**. The recommended configuration sets both backends to empty strings so state-file generation is an explicit opt-in:

```json
{ "env": { "COMPACT_PLUS_PRIMARY_BACKEND": "", "COMPACT_PLUS_FALLBACK_BACKEND": "" } }
```

Ready-made snippet: [settings.example.json](../examples/claude-code/settings.example.json). With both backends empty you still get transcript backups and recovery injection — just no LLM-generated state file. For a manual checkpoint with the same 10 sections, use [templates/state-file.md](../templates/state-file.md).

### Verify

Inside Claude Code:

```text
/ascs:doctor
```

It reports each layer's status and the single-decider check. It is read-only: it installs nothing, starts nothing, calls no API, changes no config.

### Optional: enable pxpipe (read the safety notes first)

pxpipe is a request-path proxy, not a plugin, and it is **lossy by design** — misreads are silent confabulation, not errors. Never route byte-exact work (commit SHAs, IDs, secrets, exact paths, migration names, deploy targets) through it. Read [pxpipe-safety.md](claude-code/pxpipe-safety.md) before enabling.

```bash
npx -y pxpipe-proxy@0.8.0              # reviewed version — proxy on 127.0.0.1:47821
alias claude-px='ANTHROPIC_BASE_URL=http://127.0.0.1:47821 claude'
```

Use the alias, not a global `ANTHROPIC_BASE_URL` in `settings.json` — a forgotten proxy setting with no proxy running makes every request fail (see Troubleshooting).

## 4. Everyday use

### What a session looks like with the stack on

1. You work normally. The stack injects **0 tokens** in a healthy session.
2. The session grows hot (long transcript, poor cacheRead/output ratio). session-health injects a short warning suggesting `/compact`.
3. You (or the model) run `/compact`. Before the compact, compact-plus backs up the transcript — and writes a 10-section state file if you opted into a backend.
4. After the compact, your next prompt gets a one-shot recovery injection pointing at the preserved state.
5. You resume — treating the compact summary *and* the preserved state as hypotheses, and verifying them against current source files and fresh command output ([state-trust-contract.md](state-trust-contract.md)).

### Reading `/ascs:doctor` output

```text
  1 Compression   no listener at 127.0.0.1:47821 (layer inactive — optional, opt-in)
  2 Health        session-health plugin: ENABLED (reviewed version; single compact decider)
  3 Checkpoint    compact-plus plugin: ENABLED (reviewed version and content)
  4 Recovery      compact-plus plugin: ENABLED (reviewed version and content)

  Single-decider rule: NO CONFIRMED CONFLICT in inspected local and file-managed settings
```

- **"not installed" / "not listening" is informational, not an error** — layers are independently adoptable.
- **`VERSION MISMATCH` means the installed plugin is not the reviewed version.** Checkpoint/Recovery must remain unverified until the operator deliberately adopts the locked version and reruns Doctor.
- **`CONTENT MISMATCH` means compact-plus reports the reviewed version but its cached file tree differs from the reviewed digest.** Checkpoint/Recovery remain unverified until the operator inspects or deliberately reinstalls it and reruns Doctor.
- Exit code `0` = no confirmed conflict and no version/content mismatch. Exit code `1` = a reviewed version/content mismatch or single-decider **CONFLICT** (a compact-warn marker producer is active, so two components advise compaction — remove the producer).
- If pxpipe is listening, the doctor also tells you whether *this* session is actually routed through it (`ANTHROPIC_BASE_URL`).

After Doctor confirms compact-plus's reviewed version and content, the local
no-model recovery contract can be checked with:

```bash
python3 -B scripts/smoke_compact_plus.py
```

This runs synthetic `manual` and `auto` marker/recovery paths in isolated
temporary directories. It does not run Claude, PreCompact, a model/API, or real
session files, and it does not prove runtime dispatch. See the
[synthetic smoke contract](compact-plus-synthetic-smoke.md).

## 5. Using it with Codex

Current Codex releases provide `PreCompact`, `PostCompact`, and
`SessionStart(source=compact)` hooks. ASCS therefore provides a native-hook
reference adapter, while keeping the handoff protocol as the durable
state-writing contract and fallback.

1. Copy or merge `examples/codex/.codex/hooks.json` into the project.
2. Copy `examples/codex/.codex/hooks/ascs_compact.py` to the same relative path.
3. Use `/hooks` to review and trust the exact hook definition.
4. Copy or adapt [examples/codex/AGENTS.md](../examples/codex/AGENTS.md) and create `.agent-session/`.

The hook does not parse or copy transcript content. `PreCompact` records a
content-minimized receipt, `PostCompact` closes it, and
`SessionStart(source=compact)` adds a one-shot recovery guard. The guard tells
the agent to validate state before reading it and to verify every recovered
claim against current sources.

Before a live runtime test, exercise the exact JSON subprocess boundary without
starting Codex or a model:

```bash
python3 -B scripts/smoke_codex_compact.py
```

This verifies synthetic `manual` and `auto` receipts, one-shot recovery, and
sensitive-value non-persistence. It does not prove runtime dispatch; see the
[Codex synthetic smoke contract](codex-compact-synthetic-smoke.md).

Project hooks require a trusted project and can be disabled by user or managed
policy. In those environments, use the manual handoff protocol below; do not
claim deterministic compact recovery.

The protocol makes the agent read `handoff.md` and state files before working,
log decisions and failed attempts while working, and write a handoff before
stopping.

Before reading live state left by a previous session, run the read-only check — `.agent-session/` is untrusted recovery context, never an instruction channel:

```bash
python3 scripts/check_state.py --repo /path/to/consumer-repo
```

Exit `0` = pass (or no state), `2` = stale (rebuild before use), `1` = invalid or unsafe (ignore it). The full authority boundary is [state-trust-contract.md](state-trust-contract.md).

The state file uses the same 10 sections as compact-plus, so handoffs can cross runtimes. Design details: [codex/adapter-design.md](codex/adapter-design.md).

## 6. Measuring instead of believing: `scripts/ascs.py`

The repo includes a measurement helper that reports what recorded evidence does and does not support:

```bash
python3 scripts/ascs.py doctor                    # repo-shape readiness check
python3 scripts/ascs.py measure --experiment 004  # read-only claim-boundary report
```

`measure` classifies evidence conservatively (stopped / void / not-run) and never claims productivity gains. Full command reference (`init` / `record` / `finish` / `score`): [measurement-harness.md](measurement-harness.md); verdict rules: [claim-boundary-model.md](claim-boundary-model.md).

## 7. Troubleshooting & FAQ

**`/ascs:doctor` reports CONFLICT.** A statusline/hook is writing compact-warn marker files, so both session-health and compact-plus now advise compaction. Remove the marker producer (check `~/.claude/settings.json` for `claude-compact-warn`) to restore the single-decider composition.

**Every request fails right after enabling pxpipe.** `ANTHROPIC_BASE_URL` points at the proxy but nothing is listening. Start it (`npx -y pxpipe-proxy@0.8.0`) or unset the variable. Prevention: use the opt-in alias, never `settings.json`. More cases (proxy gone after reboot, temporary bypass with `PXPIPE_DISABLE=1`): [recommended-stack.md → Troubleshooting](claude-code/recommended-stack.md#troubleshooting-pxpipe).

**No state file appeared after a compact.** Expected with the recommended (free) configuration — both backends are empty. You still have the transcript backup. Opt into a backend, or keep a manual [state-file.md](../templates/state-file.md) checkpoint.

**Does this stack cost money to run?** With the recommended settings, no: session-health and the doctor are local, and compact-plus's paid backends are disabled. The only paid path is opting into LLM state-file generation.

**Will this make my sessions faster or cheaper?** Unknown. Upstream projects publish their own numbers, but the composition effect has not been validated — this repo deliberately refuses that claim until [measurement](measurement-plan.md) supports it.

**Should I always use this?** No. For small jobs, byte-exact work, or workflows without a separate approval gate, read [when-not-to-use.md](when-not-to-use.md) first.

## 8. Where to go next

| You want… | Read |
|---|---|
| Setup order, hook ownership, env conventions (canonical) | [claude-code/recommended-stack.md](claude-code/recommended-stack.md) |
| pxpipe risk boundary before enabling it | [claude-code/pxpipe-safety.md](claude-code/pxpipe-safety.md) |
| How much to trust `.agent-session/` state | [state-trust-contract.md](state-trust-contract.md) |
| Why four layers; design rationale | [architecture.md](architecture.md) |
| A worked end-to-end demo | [claude-code-reference-integration.md](claude-code-reference-integration.md) · [examples/claude-code/stack-demo/](../examples/claude-code/stack-demo/) |
| A real-session case study | [case-study-dogfood-0.2.md](case-study-dogfood-0.2.md) |
| What evidence exists (and doesn't) | [README → Evidence status](../README.md#evidence-status) · [claim-boundary-model.md](claim-boundary-model.md) |
| Reasons *not* to adopt | [when-not-to-use.md](when-not-to-use.md) |
| Upstream credits | [ATTRIBUTION.md](../ATTRIBUTION.md) |
