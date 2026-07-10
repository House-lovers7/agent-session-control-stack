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
# Failed Attempts

## Filtered by display text

- **Date / phase**: 2026-07-05 / filter draft
- **Attempt**: Matched notes by the display label `Waiting on customer`.
- **Result**: The fictional empty-state check failed after the label was shortened to `Waiting`.
- **Cause hypothesis**: The filter used mutable UI copy instead of the stable status key recorded in state.
- **Do not retry unless**: The new attempt verifies exact status keys from a real typed source file; `state/checkpoint.md` alone is insufficient.
