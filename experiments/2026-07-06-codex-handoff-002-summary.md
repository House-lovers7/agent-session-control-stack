# Experiment 002: Codex Handoff Protocol Before/After Pair

> **Correction (2026-07-06).** The resume-time values originally published
> with v0.3.0 (baseline 143s, treated 92s, "51 seconds / ~35.7% faster") were
> measured with asymmetric clock starts that violated this experiment's own
> pre-registered rule, and have been corrected below. Most of the originally
> reported difference was measurement asymmetry, not protocol effect. Details
> in each arm's `report.md` (Correction section) and the `correction` events
> in each arm's `events.jsonl`.

## Scope

This is a manual n=1 before/after pair for the Codex handoff protocol.

It does not validate the full composition effect of `pxpipe` +
`session-health` + `compact-plus`.

## Result (corrected)

| Arm | resume_time_seconds | missed_state_files | repeated_failures | rejected_option_relapses | human_corrections | Score |
|---|---:|---:|---:|---:|---:|---|
| baseline | ~42 (was 143) | 0 | 0 | 0 | 0 | PASS |
| treated | ~33 (was 92) | 0 | 0 | 0 | 0 | PASS |

Corrected values apply the pre-registered rule — wall clock from the first
resume prompt to the first forward-progress edit — recomputed from the Codex
session logs. Operator-recorded first-edit timestamps carry second-level
precision; the session logs' first `apply_patch` completion records bound the
values at ≤57s (baseline) and ≤41s (treated). Under either reading the gap is
roughly 9–16 seconds.

## What the original numbers actually measured

- Baseline "143s" started the clock at the `interruption_reached` event,
  ~101 seconds before the resume session's first prompt existed. It measured
  interruption-to-edit wall clock, including human/session-restart overhead.
- Treated "92s" started the clock at the post-abort restart decision, 32
  seconds before the resume session was created — a third, different clock.
- The treated arm's successful resume also followed an aborted resume
  attempt. Total wall clock from interruption to the successful first edit
  was ~17 minutes (treated) vs ~2.4 minutes (baseline) — a clock dominated by
  the aborted attempt and human overhead, which is exactly why the
  pre-registered metric starts at the first resume prompt.

## Observation

Under the pre-registered rule, the treated arm resumed roughly 9 seconds
faster than baseline (~42s vs ~33s). At n=1, a single-digit-second gap is
within noise: **no speed claim is made from this pair.** Both arms passed the
score criteria (all four recovery-quality metrics at 0), so the pair is
consistency evidence that the handoff protocol workflow runs end to end — no
more than that.

## Limitations

- n=1 pair only.
- The originally published resume times were mis-measured; see the
  Correction notice above. Corrected values are reconstructed from session
  logs after the fact, not from a correctly instrumented run. A rerun with
  explicit `resume-start` events in both arms is the reliable fix.
- Baseline resume inspected `events.jsonl`, which contained a minimal
  interruption note — the baseline was not fully naive.
- The target repo is ASCS itself: both arms worked inside the repository
  that documents the protocol, so neither arm is blind and ASCS
  documentation was visible to the baseline session.
- The treated arm used root `AGENTS.md` and `.agent-session/` as the
  intervention.
- A treated resume attempt was aborted before producing usable output; it
  was recorded as `resume_attempt_aborted` and is excluded from the
  per-attempt metric (see above for the total-wall-clock view).
- All four recovery-quality metrics were 0 in both arms: the task was too
  small to exercise repeated failures or rejected-option relapses, which are
  the protocol's primary claims. The next experiment needs a task large
  enough for those to be possible.
- This result is consistency evidence for the Codex handoff protocol
  workflow, not proof of general effectiveness.
- This result does not validate the full `pxpipe` + `session-health` +
  `compact-plus` composition effect.

## Timezone convention

Event `timestamp` fields in `events.jsonl` are UTC. Clock times inside
`note` strings are JST (UTC+9) local times.

## Artifacts

- Baseline: `experiments/2026-07-06-codex-handoff-002-baseline/`
- Treated: `experiments/2026-07-06-codex-handoff-002-treated/`
