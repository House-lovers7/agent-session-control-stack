# Claude Code Stack Demo

This is a fictional, docs-only walkthrough of the Claude Code reference integration v0. It shows how the ASCS protocol layer can sit beside pxpipe, claude-code-session-health, and compact-plus without adding another compact decider.

This demo is not a benchmark, not a real session record, and does not bundle upstream code.

For setup, read [docs/claude-code/recommended-stack.md](../../../docs/claude-code/recommended-stack.md) and merge from [examples/claude-code/settings.example.json](../settings.example.json) as needed. This demo links to those files instead of copying their hook or env tables.

Demo-specific command wiring is shown in [settings.example.json](settings.example.json). It cannot drift from the shared settings because it has no overlapping env keys with [../settings.example.json](../settings.example.json); shared conventions are referenced by link, not copied.

The three adapter env vars default to empty strings:

| Env var | Adapter | Empty behavior |
|---|---|---|
| `SESSION_HEALTH_CHECK_COMMAND` | `hooks/session-health-check.sh` | Disabled; exits 1 with an explanation. |
| `COMPACT_PLUS_CHECKPOINT_COMMAND` | `hooks/compact-plus-checkpoint.sh` | Disabled; exits 1 with an explanation. |
| `PXPIPE_COMPRESS_COMMAND` | `hooks/pxpipe-compress.sh` | Disabled; exits 1 with an explanation. |

When set, each adapter `exec`s the user-supplied command and passes arguments through. The adapters do not implement upstream tools, replace plugin hooks, inject `additionalContext`, or write a compact-plus warn marker.

Attribution and upstream credits live in [ATTRIBUTION.md](../../../ATTRIBUTION.md). claude-code-session-health and this repo share a maintainer; the single-decider recommendation is argued on technical grounds, not authorship, and corrections from upstream authors take priority.

The `CLAUDE.md` marker format in [CLAUDE.md.example](CLAUDE.md.example) is illustrative and does not preempt Experiment 004 tooling.

## What to inspect

- `CLAUDE.md.example`: an illustrative ASCS protocol block for Claude Code.
- `.agent-session/handoff.md`: the resume entry point for a fictional web app task.
- `.agent-session/state/checkpoint.md`: the 10-section checkpoint shape shared with compact-plus state capture.
- `.agent-session/state/recovery-notes.md`: resumed-side verification, including one corrected discrepancy.
- `hooks/`: read-only checks, disabled examples, and manual adapter placeholders; no injecting hooks.
