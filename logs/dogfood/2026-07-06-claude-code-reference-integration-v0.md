# Dogfood 0.1 — Claude Code reference integration v0

- Date (UTC): 2026-07-06
- ASCS commit under test: `fdc1348` (Add Claude Code reference integration v0)
- Sandbox: a disposable local git repository (`_sandbox/ascs-dogfood-01`, a
  fictional note-taking CLI; local only, no remote)

**Scope.** A usability / safety smoke test of
[docs/claude-code-reference-integration.md](../../docs/claude-code-reference-integration.md)
and [examples/claude-code/stack-demo/](../../examples/claude-code/stack-demo/),
run by the maintainer on their own machine before pointing anyone else at it.
It checks that the pieces can be placed, read, and fail safely.

**This is not an efficacy measurement.** It does not test whether ASCS
improves anything, whether the protocol survives /compact, or the full-stack
composition effect — those belong to numbered experiments (Experiment 004 is
a separate, pre-registered design; this log is not part of it and must not be
cited as evidence of effect). No upstream tool was executed; adapters were
exercised only with `echo` stubs.

## What is checked / not checked

| Checked (usability / safety) | Not checked (out of scope here) |
|---|---|
| Do the pieces assemble into a usable shape? | Whether ASCS has any effect |
| Are the steps followable from the docs alone? | /compact resilience |
| Are the defaults safe (fail-safe, read-only)? | Full-stack improvement claims |
| Can a Claude Code session read the state files naturally? | Runtime defects |

## Procedure and results

### S1 — Create a sandbox target repo — PASS

Fictional minimal app (README + one stub Python file), `git init`, one
commit. No remote, no secrets, outside any real project workspace.

### S2 — Place the stack-demo files — PASS

- `CLAUDE.md.example` appended to a pre-existing sandbox `CLAUDE.md`
  (exercising the "append to or merge with, never replace" instruction);
  `ascs-protocol` markers present after the merge.
- `.agent-session/` copied as-is (fictional demo content; to be rewritten
  with real sandbox task state in S6).

### S3 — stack-doctor.sh exit codes and read-only behavior — PASS

Run from the ASCS checkout against the sandbox path:

| Case | Expected | Observed |
|---|---|---|
| All 6 state files present | exit 0 | exit 0 |
| No argument | usage on stderr, exit 2 | exit 2 |
| `state/recovery-notes.md` removed | violation message, exit 1 | exit 1, names the missing file |

Read-only verified: `git status --short -uall` in the sandbox is identical
before and after all doctor runs (including the failing one).

### S4 — Adapter fail-safe with env unset — PASS

All three adapters (`session-health-check.sh`, `compact-plus-checkpoint.sh`,
`pxpipe-compress.sh`) were run under `env -i` (clean environment): each
printed a clear explanation naming its layer, the env var to set, and that
the upstream tool must be installed by the user — then exited 1. Nothing was
executed or written. No upstream CLI name appears as an executable default.

### S5 — Stub dry-run — PASS

With each `*_COMMAND` env var set to an `echo` stub, all three adapters
exec'd the stub (arguments passed through where given) and exited 0. No
upstream tool was started at any point.

### S6 — First session: protocol adherence + handoff update — PENDING

Operator-run interactive session; not yet executed. To observe (without
coaching): does the session read `.agent-session/handoff.md` before its
first edit; how does it treat the fictional demo content vs. the real
sandbox state; does a requested protocol-conform stop update the state files.

### S7 — Fresh-session restart from state files alone — PENDING

Operator-run; not yet executed. Minimal one-line resume prompt; no
conversation log, summary, or verbal supplement. Qualitative notes only —
no timing, no scoring (that is Experiment 004's territory, under its own
pre-registered rules).

## Verdict (S1–S5 stage): usable so far

Placement, doctor, and fail-safe behavior all match the documented contract.
Final verdict waits on S6–S7.

## Friction log

1. The adapter scripts' env-unset error message points to
   `../../../../ATTRIBUTION.md` — a path that only resolves from inside the
   ASCS checkout. A user who copies `hooks/` into their own project gets a
   dangling reference. Fix candidate: name the repository (or use the full
   GitHub URL) instead of a relative path in the error text.

## Safety observations

- Defaults are safe in the tested paths: adapters are disabled-by-default
  (empty env = explain + exit 1), the doctor never writes, and nothing in
  S1–S5 invoked an upstream tool or a paid API.

## Fix candidates

- Friction #1 above (error-message path portability). Docs/demo changes are
  out of scope for this log's commit; to be applied separately if adopted.

## Explicitly not measured

Efficacy, /compact resilience, full-stack composition effect, runtime
defects. Nothing in this log supports an effectiveness claim about ASCS or
any upstream tool.
