<!-- Fictional example for the stack demo - not a real session record. -->
# Failed Attempts

## Filtered by display text

- **Date / phase**: 2026-07-05 / filter draft
- **Attempt**: Matched notes by the display label `Waiting on customer`.
- **Result**: The fictional empty-state check failed after the label was shortened to `Waiting`.
- **Cause hypothesis**: The filter used mutable UI copy instead of the stable status key recorded in state.
- **Do not retry unless**: The new attempt reads exact status keys from `state/checkpoint.md` or from a real typed source file.
