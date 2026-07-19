# ASCS Session Continuity Roadmap

Status: approved direction, 2026-07-20. This roadmap defines the next research
and implementation track; it does not claim that ASCS improves productivity or
reliability today.

## Product position

ASCS will remain a reference architecture and lightweight tooling layer. It
will become a specification, conformance suite, and research harness for
crossing compaction, interruption, and restart boundaries safely.

ASCS will not become a vector-memory database, general agent framework,
scheduler, model router, or proprietary compression model. Runtime-specific
capabilities stay behind thin adapters; ASCS owns the lifecycle contracts and
their evidence boundaries.

## Target architecture

```text
Specification
  checkpoint envelope / pinned invariants / recovery gate / verifier receipt
        |
Conformance suite
  runtime adapters + deterministic and adversarial fixtures
        |
Research harness
  compact-boundary comparisons + conservative claim verdicts
```

The intended users are runtime authors who need a contract, operators who need
a preflight gate, and researchers who need reproducible compact-boundary
evidence.

## Work tracks

### Track A — Pinned invariants and adversarial recovery

Separate project-controlled invariants from untrusted session state. Validate
repository identity, reviewed-history status, authority boundaries, and fresh
verification requirements before recovery. Grow the fixture set from direct
corruption to multi-record and source-contradiction attacks.

Initial slice: `docs/pinned-invariants-contract.md`, schema, template,
`check_recovery.py`, and deterministic fixtures.

### Track B — Verifier independence

Define a verifier receipt that binds source revision, verifier revision,
commands, result, and evidence paths. Detect verifier or expectation changes,
support held-out checks, and keep maker/checker authority separate. A mutable
test owned by the same agent is not an independent completion gate.

### Track C — Compact Boundary Benchmark

Pre-register equivalent tasks under four conditions: uninterrupted, native
compaction only, checkpoint plus compaction, and checkpoint plus fresh-session
restart. Measure constraint retention, plan retention, rejected-option relapse,
repeated failures, source/state disagreement, tool calls to forward progress,
and false completion.

Start with deterministic harness validation. Paid model runs require a separate
budget, data, and Human Approval Gate.

### Track D — Repeated-compaction drift

Measure loss and mutation after 1, 2, 4, and 8 compactions. Protect negation,
exact identifiers, permissions, decision reasons, failed attempts, and pending
conditions. Do not infer safety from a single successful summary.

### Track E — Exactly-once recovery

Add operation identifiers, idempotency keys, side-effect ledgers, and
reconciliation rules for work interrupted between execution and durable result
recording. External sends, paid calls, database writes, and deployments remain
approval-gated and out of deterministic fixtures.

### Track F — Health detector validity

Evaluate whether a health warning predicts a later failure, not merely a large
token count. Report precision, recall, false-compaction rate, and intervention
outcomes by runtime and model. Threshold tuning follows evidence rather than
becoming a universal constant.

## Adoption sequence

1. Land Track A as a local, dependency-free conformance slice.
2. Add verifier receipts before making stronger completion claims.
3. Design and freeze the compact-boundary benchmark before paid execution.
4. Add runtime adapters only when they can satisfy the same artifact contract.
5. Publish results only through the existing claim-boundary engine.

## Success and stop conditions

Success means another runtime can implement the documented artifacts, run the
same fixtures, and obtain reproducible verdicts without adopting ASCS internals.
Research success requires valid comparisons, not hook invocation alone.

Stop or narrow the track when it duplicates an upstream runtime, cannot be
verified independently, increases authority from state, requires paid execution
without an approved budget, or produces only token savings without semantic
recovery evidence.

## Evidence basis and uncertainty

This direction follows primary sources reviewed on 2026-07-20, including
research on active context management, plan loss, governance loss during
compaction, trustworthy memory transitions, structured eviction, and
verification-gated harnesses. The source review is recorded in
`docs/implementation-notes/2026-07-20-loop-engineering-external-review.md`.

Most 2026 research cited in that review is preprint evidence. It supports the
problem framing and experiment design, but does not prove ASCS's composition
effect. That effect remains unvalidated until this repository records valid,
non-void comparisons.
