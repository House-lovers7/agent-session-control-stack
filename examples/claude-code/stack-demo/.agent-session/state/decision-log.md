<!-- Fictional example for the stack demo - not a real session record. -->
# Decision Log

---

## Use explicit status keys instead of display labels

- **Date / phase**: 2026-07-05 / triage filter design
- **Decision**: Store filter logic against explicit status keys and keep display labels separate.
- **Options considered**:
  - Display labels such as "Waiting on customer" - rejected because label copy may change and should not alter filtering behavior.
  - Stable keys such as `waiting_on_customer` and `unassigned` - **chosen** because they are byte-exact values that can be verified from state files before editing.
- **Constraints that drove it**: The restart protocol requires exact values to come from disk, not from summaries or memory.
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
