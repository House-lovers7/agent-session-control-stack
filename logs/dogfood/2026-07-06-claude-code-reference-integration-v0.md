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

### S6 — First session: protocol adherence + handoff update — PASS (with notes)

**Method (and its limits).** S6/S7 were run as fresh subagent sessions
spawned from the maintainer's Claude Code session, with the sandbox
`CLAUDE.md` content injected verbatim at the top of the prompt to
approximate Claude Code's automatic project-instruction loading. This is
not a full interactive session, and the prompt asked for a chronological
file-access log at the end (a mild observation effect). Qualitative
smoke-test evidence only.

Observed, first session (task: implement the stub function + a test; no
mention of `.agent-session/` outside the injected CLAUDE.md):

- Read `.agent-session/handoff.md` **first**, then all five state files,
  **before** opening any source file.
- Detected the mismatch between the fictional demo content (a made-up
  "Beacon Board" web app pointing at a nonexistent source file) and the
  real sandbox state, and recorded it in `state/recovery-notes.md` instead
  of acting on the fiction.
- On its own initiative, updated `handoff.md` (accurate: what was done,
  test result, uncommitted status) and `recovery-notes.md` before stopping.
- **Partial adherence without a nudge**: `decision-log.md` and
  `checkpoint.md` were only updated after an explicit "update
  `.agent-session` per the protocol" follow-up (then correctly: the
  adopted/rejected storage decision, a phase-boundary checkpoint).
  `failed-attempts.md` was correctly left alone (no failures occurred).

### S7 — Fresh-session restart from state files alone — PASS

A brand-new session (zero shared memory) received only the injected
CLAUDE.md and a one-line resume prompt ("continue the previous session's
task"). No conversation log, summary, or verbal supplement. Observed:

- Read `handoff.md` first, then every state file, before any source file.
- Treated the handoff as a hypothesis and verified it against the source:
  re-read the implementation and test, re-ran the test suite (passed),
  cross-checked `git status` against the handoff's summary.
- Concluded the task was genuinely complete, and **did not redo any
  completed work and did not fabricate a new task** — it reported
  completion, recorded one real discrepancy it found (a generated
  bytecode directory missing from the handoff's git summary), and updated
  `recovery-notes.md` and `handoff.md` per the protocol.

## Verdict: usable

S1–S5: placement, doctor, and fail-safe behavior all match the documented
contract. S6–S7: under the subagent approximation above, the protocol was
followed at resume time exactly where it matters most — handoff read
first, summaries verified against source, no redone work. The one gap is
mid-work adherence (S6 notes), which needed a nudge.

## Friction log

1. The adapter scripts' env-unset error message points to
   `../../../../ATTRIBUTION.md` — a path that only resolves from inside the
   ASCS checkout. A user who copies `hooks/` into their own project gets a
   dangling reference. Fix candidate: name the repository (or use the full
   GitHub URL) instead of a relative path in the error text.
2. `state/current-plan.md` is in the protocol's read list but no protocol
   rule ever updates it — the fictional demo plan survived both S6 sessions
   untouched and stale. Fix candidate: add current-plan to the
   before-stopping update list (or state explicitly that the handoff
   supersedes it).
3. Session artifact, not a doc defect: after a later checkpoint refresh,
   the handoff's pointer note ("checkpoint predates the notes task") went
   stale until the S7 session rewrote it. The protocol's trust rule
   ("everything here is a hypothesis") is what caught it — worth keeping
   prominent.

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
