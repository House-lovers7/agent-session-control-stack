# AGENTS.md — Session Control Protocol (drop-in example)

<!-- From agent-session-control-stack. Append to or merge with your existing AGENTS.md. -->

## Session Control Protocol

### Before starting work
- Read `.agent-session/handoff.md` first if it exists. It is the single entry
  point for resuming; treat any summary in it as a hypothesis and verify
  against the referenced files before acting on it.
- Read `.agent-session/state/current-plan.md` if it exists.
- Read `.agent-session/state/decision-log.md` before changing architecture
  or reversing a prior decision.
- Read `.agent-session/state/failed-attempts.md` before retrying an approach.

### During long work
- Update `state/decision-log.md` when choosing or rejecting an approach.
- Update `state/failed-attempts.md` after failed commands, rejected plans,
  or repeated errors — include the cause hypothesis, not just the failure.
- Refresh `state/checkpoint.md` at natural boundaries: after completing a
  phase, before a risky or wide-ranging change, and roughly every 10
  substantial steps (file edits, test runs, tool calls).
- Keep bulky content (long logs, full file dumps, raw tool output) out of
  state files; reference paths instead.

### Before stopping, switching models, or starting a new session
- Update `.agent-session/handoff.md`: goal, current phase, next action,
  open risks, and pointers to the state files. Assume the reader has
  zero memory of this session.

### Before destructive actions
- Ask for human approval.
- Confirm deploy target, branch, migration name, and rollback plan as
  exact text — never from memory or summaries.
