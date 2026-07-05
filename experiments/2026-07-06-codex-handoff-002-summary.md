# Experiment 002: Codex Handoff Protocol Before/After Pair

## Scope

This is a manual n=1 before/after pair for the Codex handoff protocol.

It does not validate the full composition effect of `pxpipe` +
`session-health` + `compact-plus`.

## Result

| Arm | resume_time_seconds | missed_state_files | repeated_failures | rejected_option_relapses | human_corrections | Score |
|---|---:|---:|---:|---:|---:|---|
| baseline | 143 | 0 | 0 | 0 | 0 | PASS |
| treated | 92 | 0 | 0 | 0 | 0 | PASS |

## Observation

The treated arm resumed 51 seconds faster than baseline, approximately 35.7% shorter resume time.

Both arms passed the current score criteria.

## Limitations

- n=1 pair only.
- Baseline resume inspected `events.jsonl`, which contained a minimal
  interruption note.
- The treated arm used root `AGENTS.md` and `.agent-session/` as the intervention.
- A treated resume attempt was aborted before producing usable output; it was
  recorded as `resume_attempt_aborted`.
- This result is consistency evidence for the Codex handoff protocol workflow, not
  proof of general effectiveness.
- This result does not validate the full `pxpipe` + `session-health` +
  `compact-plus` composition effect.

## Artifacts

- Baseline: `experiments/2026-07-06-codex-handoff-002-baseline/`
- Treated: `experiments/2026-07-06-codex-handoff-002-treated/`
