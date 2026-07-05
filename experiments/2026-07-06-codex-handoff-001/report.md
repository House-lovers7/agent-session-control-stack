# Experiment Report

## Metadata

- Name: `codex-handoff-001`
- Runtime: `codex`
- Target repo: `.`
- Created at: `2026-07-05T16:42:27+00:00`

## Task Summary

Experiment 001: Codex handoff protocol.

Goal: collect the first lightweight evidence that the `AGENTS.md` protocol plus
`.agent-session` state/handoff templates make restart work easier to resume.

Condition: repository-local Codex session using the documented protocol and the
Phase 2 measurement harness. No pxpipe proxy, Claude Code hook, compact-plus
backend, Codex wrapper, transcript parser, dashboard, or upstream integration
was run.

Done definition: create a real experiment directory, record recovery/state
events, finish metrics, and score the result.

## Events

- See `events.jsonl`.

## Result

| Metric | Value |
|---|---:|
| resume_time_seconds | 60 |
| missed_state_files | 0 |
| repeated_failures | 0 |
| rejected_option_relapses | 0 |
| human_corrections | 0 |

Score: **PASS**

Failed criteria: 0

## Notes

- This is a single lightweight evidence run, not a controlled before/after
  experiment.
- `resume_time_seconds` is an approximate wall-clock estimate from resuming the
  task to making forward progress by creating the experiment.
- The result validates the handoff measurement workflow only. It does not
  validate the composition effect of pxpipe + session-health + compact-plus.
