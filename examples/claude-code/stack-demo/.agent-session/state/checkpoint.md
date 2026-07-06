<!-- Fictional example for the stack demo - not a real session record. -->
# Compact Prep State

## Active Plan
Finish the fictional Beacon Board triage filter demo. The active plan is in `state/current-plan.md`.

## Current Phase
Filter behavior design is underway. Done for this phase means the `needs_reply` rule is represented using stable status keys and the next session knows which exact values to use.

## TaskList Summary
- Done: Chose stable status keys over display labels.
- Done: Logged the rejected display-label approach.
- Underway: Define `needs_reply` as `waiting_on_customer` plus `unassigned`.
- Not started: Verify the fictional empty state after filtering.

## Session Decisions
- Adopted stable status keys for filter logic because display labels are mutable.
- Rejected a real analytics event because this is a docs-only session-boundary demo.

## Constraints and Blockers
- This is a fictional example, not a real repository or session record.
- Do not add product code, external sends, deploys, migrations, paid API paths, or destructive commands.
- Exact status keys currently known: `new`, `waiting_on_customer`, `unassigned`, `closed`.
- The remembered summary may incorrectly say `waiting_customer`; verify from this file instead.

## Worker Topology
No subagents or workers are in flight. A future resumer should continue as a single operator session.

## Skills Invoked
No runtime skill or hook has been invoked in this fictional demo. The example relies on manual state-file maintenance.

## Editing Files
- `.agent-session/handoff.md`: resume entry point.
- `.agent-session/state/current-plan.md`: active fictional plan.
- `.agent-session/state/decision-log.md`: adopted and rejected options.
- `.agent-session/state/failed-attempts.md`: failed display-label attempt.
- `.agent-session/state/recovery-notes.md`: resumed-side verification.

## Failed Attempts
The display-label filter failed because label copy changed. See `state/failed-attempts.md`.

## Recovery Notes
On resume, verify the exact status key `waiting_on_customer` from this checkpoint before editing. If any summary says `waiting_customer`, treat that as drift and use the on-disk state.
