# Claude Code Reference Integration v0

**Status**: reference integration. The composition effect has NOT been measured. Experiment 004: design draft published, no results yet (protocol layer only, operator-driven). This integration does not claim that Claude Code's long-session problems are solved.

## 1 What this integrates

The 3-tool detail lives in [docs/claude-code/recommended-stack.md](claude-code/recommended-stack.md). This document only adds where the ASCS protocol layer fits.

| Component | Maintainer / source | Responsibility in this integration |
|---|---|---|
| pxpipe | teamchong | Compression: reduces bulky request-path context while byte-exact work stays out of the compressed path. |
| claude-code-session-health | House-lovers7 | Health detection and the single compact decider. |
| compact-plus | u-ichi | Checkpoint and recovery around compaction. |
| ASCS protocol | This repo | Runtime-agnostic state contract: `.agent-session/` plus the `CLAUDE.md` protocol block. This is the only layer that works across both boundary kinds below. |

## 2 Two boundaries, one contract

### A. Compaction boundary

```text
normal work
  -> pxpipe proxy compresses eligible request-path bulk
  -> session-health monitors live-segment health
  -> hot session
  -> session-health UserPromptSubmit advisory (~60 tokens)
  -> /compact is chosen by the single decider
  -> PreCompact:
       compact-plus backs up the transcript
       compact-plus may create the opt-in paid 10-section state file
  -> compaction
  -> PostCompact:
       compact-plus writes a recovery marker
       session-health counters reset via the compact_boundary record
  -> next UserPromptSubmit:
       compact-plus performs one-shot recovery injection
  -> model re-reads `.agent-session/` and the state file from disk
       summary is hypothesis, source is truth
```

### B. Fresh-session restart boundary

```text
normal work
  -> no compaction lifecycle hooks fire
  -> before stopping, the ASCS protocol updates `.agent-session/handoff.md`
     and state files
  -> new session starts
  -> the `CLAUDE.md` protocol block says to read `.agent-session/handoff.md`
     before working
  -> state files are the only carrier across the boundary
```

| State surface | Writer | Boundary coverage |
|---|---|---|
| `.agent-session/*` | The model under protocol plus the operator | Both boundaries |
| `~/.claude/backups/transcripts/*` | compact-plus `PreCompact` | Boundary A only |
| compact-plus state file | compact-plus LLM backend, opt-in | Boundary A only |
| warn marker | NOBODY in this stack | Producer not installed: the single-decider rule made concrete |

The compact-plus state capture and the ASCS `.agent-session/` files are complementary, not competing. They use the same 10-section snapshot shape from [templates/state-file.md](../templates/state-file.md): automated-at-compact versus manual-at-any-boundary.

## 3 Single compact decider

Rules 1-3 are defined in [docs/hook-responsibilities.md](hook-responsibilities.md). This integration adds two protocol rules:

Rule 4: the ASCS `CLAUDE.md` protocol block never mentions compaction timing or thresholds. A second "compact now" voice would defeat the single-decider design.

Rule 5: nothing shipped in the demo writes the warn marker, injects `additionalContext`, or registers as a hook.

## 4 Hook surface: what v0 adds (nothing)

v0 adds zero injecting hooks. The existing injection token budget is unchanged: 0 normally, ~60 while hot, and a few hundred once after compact, as summarized in [docs/claude-code/recommended-stack.md](claude-code/recommended-stack.md).

The demo's `hooks/` directory contains only a read-only checker and a disabled placeholder.

## 5 Byte-exact values policy

The pxpipe safety boundary and existing env/control tables live in [docs/claude-code/pxpipe-safety.md](claude-code/pxpipe-safety.md). Operationally:

Rule B1: State files are the canonical place for non-secret work state that must survive a context boundary, such as SHAs, file paths, migration names, exact command names, and unresolved TODOs. Do not use an image, compacted transcript, or generated summary as the source of truth for these values. Secrets must not be written into .agent-session/ state files; use an approved secret store or a redacted reference instead. For sessions that may involve secrets, run with `PXPIPE_DISABLE=1` or use an approved secret store / redacted placeholder reference.

B2: prefer a fresh read of state files over trusting compressed or summarized copies. This is an operational rule, not a claim about pxpipe internals.

B3: sessions involving deploys, migrations, or destructive commands run with `PXPIPE_DISABLE=1`, in the same family as the incident rule in [docs/claude-code/pxpipe-safety.md](claude-code/pxpipe-safety.md).

## 6 The demo

[examples/claude-code/stack-demo/](../examples/claude-code/stack-demo/) is a fictional worked demo:

- `README.md` explains the purpose, non-goals, setup pointers, and attribution.
- `settings.example.json` wires only demo-specific adapter command env vars and leaves them disabled by default.
- `CLAUDE.md.example` shows an illustrative ASCS protocol block for Claude Code.
- `.agent-session/handoff.md` is the resume entry point for a made-up web app session.
- `.agent-session/state/current-plan.md` records the active fictional plan.
- `.agent-session/state/decision-log.md` records one adopted and one rejected option.
- `.agent-session/state/failed-attempts.md` records one failed attempt with a cause hypothesis.
- `.agent-session/state/checkpoint.md` uses the exact 10 sections from [templates/state-file.md](../templates/state-file.md).
- `.agent-session/state/recovery-notes.md` is written from the resumed side and demonstrates resolving remembered summary drift by re-reading source state files.
- `hooks/stack-doctor.sh` performs read-only checks.
- `hooks/session-start.example.sh` is disabled at the first executable statement.
- `hooks/session-health-check.sh`, `hooks/compact-plus-checkpoint.sh`, and `hooks/pxpipe-compress.sh` are manual adapter placeholders. They run only a user-supplied command from env and do not implement upstream tools.

Look for two things: the demo crosses a fresh-session restart boundary using only state files, and it does not add a second compact decider.

## 7 Evidence status

This integration does not claim that Claude Code's long-session problems are solved.

1. Upstream self-reported numbers, attributed in [ATTRIBUTION.md](../ATTRIBUTION.md).
2. Experiment 004: design draft published, no results yet (protocol layer only, operator-driven).
3. The composition effect of running all layers together has not been measured.

## 8 Attribution & disclosure

See [ATTRIBUTION.md](../ATTRIBUTION.md). claude-code-session-health and this repo share a maintainer; the single-decider recommendation is argued on technical grounds, not authorship, and corrections from upstream authors take priority.

## 9 Relation to experiments

This document and demo change nothing under `experiments/` or `docs/experiment-*`. Experiment 004 tests the protocol layer alone across a fresh-session restart boundary: design draft, no results yet. A future separately-numbered experiment would cover the compaction boundary and full stack.
