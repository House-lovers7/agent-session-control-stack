# Experiment Report

## Metadata

- Name: `codex-handoff-001`
- Runtime: `codex`
- Target repo: `/path/to/target`
- Created at: `2026-07-06T00:00:00+00:00`

## Task Summary

Measure whether the Codex handoff protocol reduces restart drift during a real
task. Define the done condition before judging the result.

## Events

- See `events.jsonl`.

## Result

| Metric | Value |
|---|---:|
| resume_time_seconds | 180 |
| missed_state_files | 0 |
| repeated_failures | 0 |
| rejected_option_relapses | 0 |
| human_corrections | 1 |

Score: **PASS**

Failed criteria: 0

## Notes

Manual measurement only. No hook, proxy, wrapper, or transcript parser was run.
