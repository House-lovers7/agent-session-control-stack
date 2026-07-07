# ASCS Claim-Boundary Model

The claim-boundary engine (`compute_claim_verdict` in `scripts/ascs.py`) is a
pure function: it takes parsed experiment evidence (events per arm per pair,
plus a closeout flag) and returns a structured verdict. All file reading lives
in a thin I/O layer (`experiment_004_evidence`); the engine itself performs no
I/O. `measure` never writes `events.jsonl`, `report.md`, `experiment.json`, or
any target-repo file. The only write `measure` can perform is the report path
explicitly requested with `--output`, and protected evidence paths are rejected
fail-closed.

The design bias throughout: **prefer disallowing claims over inflating weak
evidence.** A claim not present in `allowed_claims` must not be made in READMEs,
posts, or reports.

## Pair classification

Evaluated in this order (first match wins):

1. **VOID condition N** — an explicit `void-pair` event exists. No
   treated-vs-baseline claim, ever.
2. **VOID (scope_differs audit)** — a `pair-checkpoint-audit` event records
   `scope_differs=True` but no `void-pair` event has landed yet. An operator
   scope judgment is strong evidence on its own, so the engine fails closed
   and voids the pair immediately.
3. **NOT RUN** — no arm recorded `arm_start`. An unrun pair is *not* failure
   evidence; its claim boundary is "incomplete pair; not a failure".
4. **INCOMPLETE** — arms started but did not both reach the interruption
   checkpoint, or reached it without a recorded `pair-verdict`.
5. **VALID COMPARISON** — both arms started, checkpointed, and recorded
   `pair-verdict` events. Even then the claim boundary is "consistency
   evidence only; not causality".

## Experiment classification

- **STOPPED / no valid comparison** — a closeout document exists and no valid
  pair remains, or any pair is void. Claim boundaries follow the closeout.
- **COMPLETE / valid comparisons available** — every pair is a valid
  comparison. Evidence level is still consistency, not causality.
- **INCOMPLETE / no valid comparison yet** — everything else.

Evidence levels: `evidence-loop validation only` (zero valid pairs) or
`consistency evidence only (N valid pair(s)); not causality`. There is no
evidence level that licenses causal, productivity, speed, model-superiority,
or runtime-superiority claims from a single experiment.

## Metric trust rules

- `resume_time_seconds` is trusted only when derived from `resume-start` and
  `first-progress-edit` events (`derive_resume_time_from_events`). Untrusted
  values never appear in `allowed_claims`.
- `failing_count` differences across arms are **observed facts only**. They
  never imply `scope_differs` (that requires an explicit audit event) and
  never support performance claims.
- Any metric without event-level support is an unsupported metric and cannot
  back an allowed claim.

## Layer claim boundaries

ASCS models three upstream projects as independent layer contracts. It bundles
and reimplements none of them (`CLAIM_LAYERS` in `scripts/ascs.py`).

ASCS helper/harness events are tracked separately as **ASCS evidence-loop**
evidence. For example, Experiment 004 has ASCS checkpoint-recording evidence
(`arm_start`, `interruption_reached`, `pair-checkpoint-audit`, `void-pair`),
but that is not compact-plus runtime evidence.

| Layer | Upstream | Evidence detected from | Key overclaims always disallowed |
| --- | --- | --- | --- |
| compression | pxpipe (teamchong) | `compression`/`pxpipe` events | token/bill reduction implies semantic correctness; safe for byte-exact values |
| health_detection | claude-code-session-health (House-lovers7) | `health` events | detection alone improved productivity; accuracy claims without labeled events |
| checkpoint_recovery | compact-plus (u-ichi) | explicit compact-plus runtime markers such as `compact-plus`, `state-capture`, or `recovery-injection` events | compact-plus runtime recovery claims without compact-plus runtime events |

Layer statuses are mechanism-level only: `no evidence`, `mechanism events
recorded; no validated claims`. The README's four-layer view (Compression,
Health Detection, Checkpointing, Recovery) is represented by the ASCS
evidence-loop section for harness evidence and by upstream layer evidence only
when upstream runtime markers exist. compact-plus conceptually covers
Checkpointing and Recovery, but Experiment 004 did not exercise compact-plus
runtime behavior. A layer's `improved productivity` claim is disallowed even
when valid pairs exist, because valid pairs are consistency evidence.

`pair-checkpoint-audit` events are harness audit evidence, not layer mechanism
evidence, and are excluded from layer detection.

## Composition claim boundary

The full-stack composition claim is allowed to reach at most **composition
consistency evidence only; not causality**, and only when both hold:

1. every layer has isolated (non-"no evidence") mechanism evidence, and
2. at least one valid, non-void pair exists in the same experiment.

Until then the status is `no composition evidence`. These stay disallowed in
all cases: "Running all three layers together improves productivity", "The
full-stack composition effect is validated", "Single-layer results transfer
additively to the composition".

## Verdict structure

`compute_claim_verdict` returns: `experiment_status`, `pair_statuses`,
`evidence_level`, `observed_facts`, `allowed_claims`, `disallowed_claims`,
`next_required_evidence`, `reasons`, `blockers`, plus the three-way split the
reports render: `layer_evidence` (per-layer), `composition_evidence`, and
`unsupported_claims` (experiment + layer + composition overclaims, deduped).

Render with:

```sh
python3 scripts/ascs.py measure --experiment 004                      # text
python3 scripts/ascs.py measure --experiment 004 --format markdown    # markdown to stdout
python3 scripts/ascs.py measure --experiment 004 --format markdown --output reports/experiment-004-claim-boundary.md
python3 scripts/ascs.py measure --experiment-dir experiments/<dir>    # any experiment directory (arms = events.jsonl holders; p<N> tokens pair them)
```

## Future design sketch (not implemented)

- **Doctor contamination report (red/yellow/green)** — reclassify `doctor`
  output: red = claim-invalidating findings (scaffold contamination, void
  conditions present, missing preregistration), yellow = weakened evidence
  (optional metrics missing, unverified assumptions), green = clean. Red must
  fail closed the same way `scope_differs` does here. Out of scope for the
  verdict engine; belongs to the doctor command.
- **HTML report** — a second renderer over the same verdict dict; no engine
  changes required.
