# Implementation Notes: GitHub Issue #5

## Plan Reference

- GitHub Issue [#5](https://github.com/House-lovers7/agent-session-control-stack/issues/5)
- ACOS run `20260710T120031Z-Fix-GitHub-issue-5-enforce-trustworthy-e`

## Decisions

- New records use event schema v1. Unknown fields/versions, unsafe names,
  non-UTC timestamps, multi-line notes, and invalid optional metadata fail
  closed.
- Existing 49 unversioned repository events are not rewritten. Legacy reads
  require an explicit `allow_legacy=True` code path and are disclosed in the
  verdict's observed facts.
- Pair validity requires exactly one baseline and one treated arm, lifecycle
  ordering, and coherent verdict notes. Directory grouping alone never grants
  comparison semantics.
- Resume timing uses a small state machine; abort clears both the clock and any
  progress for that attempt.
- Metric validation is enforced at argparse, direct finish, scoring, and pure
  score-calculation boundaries.

## Deviations

- What: Event schema v1 does not cryptographically attest that a runtime event
  came from an upstream tool.
  Why: This repository is intentionally a manual, local measurement harness
  and has no signed upstream event source or trust root.
  Choice: Enforce structural, lifecycle, delimiter, pair-semantic, and claim
  boundaries; continue to describe accepted layer events as mechanism-level
  evidence only.
  Reconsider: yes, if upstream tools publish authenticated event contracts.

## Discovered Unknowns

- [UK] The previous generic pair grouping treated `p<N>` directory syntax as
  if it also proved baseline/treated semantics.
- [UU] The old layer detector used unbounded substring matching, so unrelated
  names could jointly unlock composition consistency status.
- [KU] Legacy event history is structurally valid but has no explicit schema
  marker; silent acceptance would erase that distinction.

## Open Questions

- Whether a future schema should carry signed provenance from pxpipe,
  session-health, or compact-plus. No current upstream contract supports it.

## Follow-ups

- If schema v2 is proposed, add an explicit migration reader; never reinterpret
  v1 or legacy records in place.
