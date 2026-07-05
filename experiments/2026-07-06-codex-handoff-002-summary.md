# Experiment 002: Codex Handoff Protocol Before/After Pair

## Scope

This is a manual n=1 before/after pair for the Codex handoff protocol.

It does not validate the full composition effect of pxpipe + session-health +
compact-plus.

## Result

| Arm | resume_time_seconds | missed_state_files | repeated_failures | rejected_option_relapses | human_corrections | Score |
|---|---:|---:|---:|---:|---:|---|
| baseline | 143 | 0 | 0 | 0 | 0 | PASS |
| treated | 92 | 0 | 0 | 0 | 0 | PASS |

## Observation

The treated arm resumed 51 seconds faster than baseline, approximately 35.7%
shorter resume time.

## Limitations

- n=1 pair only.
- Baseline resume inspected `events.jsonl`, which contained a minimal
  interruption note.
- Treated arm used root `AGENTS.md` and `.agent-session/` as the intervention.
- The result is consistency evidence for the handoff protocol workflow, not
  proof of general effectiveness.
