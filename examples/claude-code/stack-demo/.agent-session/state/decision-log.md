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
# Decision Log

---

## Use explicit status keys instead of display labels

- **Date / phase**: 2026-07-05 / triage filter design
- **Decision**: Store filter logic against explicit status keys and keep display labels separate.
- **Options considered**:
  - Display labels such as "Waiting on customer" - rejected because label copy may change and should not alter filtering behavior.
  - Stable keys such as `waiting_on_customer` and `unassigned` - **chosen** because they can be re-read from typed product source before editing.
- **Constraints that drove it**: The restart protocol treats state as a hint and requires exact values to come from current authoritative source, not summaries or memory.
- **Revisit if**: The fictional app grows a typed enum source that becomes the single authority for status keys.

---

## Do not add a real analytics event in the demo

- **Date / phase**: 2026-07-05 / demo scoping
- **Decision**: Keep analytics out of the fictional demo.
- **Options considered**:
  - Add an `triage_filter_changed` event - rejected because it would imply product integration and distract from the session-boundary example.
  - Record only state-file changes - **chosen** because this demo is docs-only and should not imply runtime instrumentation.
- **Constraints that drove it**: The demo must not be a real session record and must not modify product code.
- **Revisit if**: A separately-scoped docs example is created specifically for analytics instrumentation.
