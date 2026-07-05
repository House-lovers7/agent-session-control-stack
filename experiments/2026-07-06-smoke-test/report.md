# Experiment Report

## Metadata

- Name: `smoke-test`
- Runtime: `codex`
- Target repo: `.`
- Created at: `2026-07-05T16:29:19+00:00`

## Task Summary

Harness smoke test. The task was exercising `scripts/ascs.py` end to end
(init → record → finish → score) against this repository. Done definition:
all four commands complete and produce the expected files. The metrics below
validate the harness workflow only — this run is not a before/after
measurement and not evidence for the stack or the handoff protocol.

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

<!-- One to three lines of qualitative observations. -->
