<!-- Fictional example for the stack demo - not a real session record. -->
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
Re-read `state/checkpoint.md` and resolved the discrepancy in favor of the source file: the key is `waiting_on_customer`. Summary is hypothesis, source is truth.
