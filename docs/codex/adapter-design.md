# Codex Adapter Design

Codex has no equivalent of Claude Code's compact lifecycle hooks (`PreCompact` / `PostCompact`). This adapter does **not** try to emulate them. Instead, it implements the same two layers — Checkpoint and Recovery — as a **session handoff protocol**: a small set of files the agent reads before working and updates as it works, declared in `AGENTS.md`, which Codex reads before starting work.

Framing matters: this is not a "compact workaround." It is a protocol for handing work across session boundaries of any kind — a new session, a model switch, or an interruption.

## Layout

```
<your repo>/
  AGENTS.md                     # declares the session protocol
  .agent-session/
    state/
      current-plan.md           # the approved plan, in execution order
      decision-log.md           # chosen and rejected options, with reasons
      failed-attempts.md        # failed approaches + cause hypotheses
      recovery-notes.md         # traps and environment quirks for resumers
      checkpoint.md             # latest 10-section state snapshot
    handoff.md                  # the single entry point for resuming
```

- Add `.agent-session/` to `.gitignore` — it is working memory, not product history
- `checkpoint.md` uses the same 10 sections as compact-plus state files ([templates/state-file.md](../../templates/state-file.md)), so a handoff can cross runtimes: a Claude Code session's state capture is readable by a Codex session, and vice versa
- Apply the [state trust contract](../state-trust-contract.md): state is untrusted recovery context with repository/branch/commit/session/expiry metadata, never an authority or secret store

## The protocol

The full drop-in `AGENTS.md` text lives at [examples/codex/AGENTS.md](../../examples/codex/AGENTS.md). In summary:

**Before starting work** — validate the metadata first. Ignore a repository mismatch; treat branch/commit mismatch or expiry as stale. Then read `handoff.md` as a hypothesis and verify referenced items against current source and command output. Read `current-plan.md`; read `decision-log.md` before changing architecture; read `failed-attempts.md` before retrying an approach.

**During long work** — log decisions and failures as they happen (with cause hypotheses, not just symptoms). Refresh `checkpoint.md` at natural boundaries: after a phase, before a risky change, roughly every 10 substantial steps. Keep bulky content out of state files; reference paths instead.

**Before stopping, switching models, or starting a new session** — update `handoff.md` for a reader with zero memory of this session: goal, current phase, next action, open risks, pointers into `state/`.

**Before destructive actions** — ask for human approval, and confirm deploy target, branch, migration name, and rollback plan as exact text, never from memory or summaries.

**Retention and rollback** — keep state ignored, use a maximum seven-day expiry, remove it when the task ends, and keep any ignored pre-rewrite rollback copy for at most 24 hours. A restored copy receives the same trust checks. Never store secrets, credentials, raw customer/personal data, or verbatim untrusted instructions.

## What the Health layer becomes here

Codex does not expose a metrics surface comparable to what session-health measures — we have not verified whether its session logs could provide one — so the Health layer degrades to proxy signals: elapsed time, accumulated tool calls and edited files, repeated test failures, a diff that has grown large. The protocol treats these as triggers to refresh `checkpoint.md` and consider a handoff. A wrapper that watches these signals automatically is a roadmap item, not part of this adapter.

## Honest comparison with the Claude Code binding

| | Claude Code | Codex |
|---|---|---|
| Enforcement | hooks fire deterministically, regardless of the agent's intent | the agent itself must follow the protocol — adherence is probabilistic |
| State location | plugin-managed (`$TMPDIR`, `~/.claude/backups/`) | in-repo `.agent-session/`, visible and editable |
| Guarantee | strong | **weak — measure adherence before trusting it** (see [measurement-plan.md](../measurement-plan.md)) |

This asymmetry is the design, not a gap to be papered over: the same layer contracts ([adapter-interface.md](../adapter-interface.md)), implemented on each runtime's native surface, with the weaker guarantee stated plainly.
