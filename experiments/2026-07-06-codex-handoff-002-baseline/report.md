# Experiment Report

## Metadata

- Name: `codex-handoff-002-baseline`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/agent-session-control-stack`
- Created at: `2026-07-05T17:29:10+00:00`

## Task Summary

Experiment 002, **baseline arm**. Pre-registered before the session started;
judgment rules below must not be changed after work begins.

**Task**: Add a short documentation section explaining when NOT to use Agent
Session Control Stack.

**Expected output / done definition**:
- `docs/when-not-to-use.md` with at least 3 "do not use yet" cases
- `README.md` (and `README.ja.md`) link to it
- No new claims about measured composition effect

**Condition (baseline)**: no ASCS `AGENTS.md` protocol at the repo root, no
ASCS `.agent-session/`. Plain Codex session on branch `exp-002-baseline`.

**Interruption design**: end the session after `docs/when-not-to-use.md` is
drafted — and after at least one structuring option has been explicitly
rejected in-session — but before the README links and the final consistency
pass. Resume in a fresh Codex session given only the repo and the original
task statement (no state files, no transcript).

**Judgment rules (pre-registered)**:
- `resume_time_seconds`: wall clock from the first resume prompt to the first
  forward-progress edit that survives into the final deliverable.
- `missed_state_files`: pre-interruption artifacts or decisions (files
  created/edited, chosen/rejected options) the resumed session did not
  account for before acting.
- `repeated_failures`: an approach that visibly failed before the
  interruption, re-executed unchanged after resume.
- `rejected_option_relapses`: an option explicitly rejected before the
  interruption, re-proposed after resume without a new stated reason.
- `human_corrections`: human messages needed to redirect the resumed session,
  excluding re-stating the task itself.

**Order and adoption**: baseline runs first, treated second, on separate
branches from the same base commit. The deliverable that ships is chosen by
human review after both runs; the other branch is discarded. n=1 pair —
consistency evidence only, not causality (docs/measurement-plan.md §2).

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
