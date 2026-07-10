<!-- Fictional example for the stack demo - not a real session record. -->
<!-- ascs-state-metadata
state_schema_version: 1
repository: example/beacon-board
branch: feature/triage-filter
commit: 1111111111111111111111111111111111111111
session_id: demo-session-002
updated_at: 2026-07-10T00:00:00+00:00
expires_at: 2026-07-17T00:00:00+00:00
-->
# Recovery Notes

## Resume verification
Read `handoff.md`, `state/current-plan.md`, `state/decision-log.md`, `state/failed-attempts.md`, and `state/checkpoint.md` before continuing.

## Verified from state files
- The fictional app is Beacon Board, a team dashboard for triaging customer notes.
- The next action is the `needs_reply` filter.
- The exact status keys are `new`, `waiting_on_customer`, `unassigned`, and `closed`.
- The failed approach matched display labels instead of stable keys.

## Discrepancy found
The remembered summary said the relevant customer-waiting key was `waiting_customer`.

## Resolution
Re-read `state/checkpoint.md` and found the candidate `waiting_on_customer`. Because this is a docs-only fictional demo with no product source, the discrepancy remains unverified; a real session must resolve it against current typed source. Summary and state are hypotheses, source is truth.
