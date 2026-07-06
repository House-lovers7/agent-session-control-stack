# Experiment Report

## Metadata

- Name: `codex-handoff-003-p1r-treated`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T07:49:07+00:00`

## Task Summary

Experiment 003, **re-registered Pair 1r, treated arm** (runs second in Pair
1r). Pre-registered before any session work; nothing below may change after
work begins. Same task (T1' = partial REVOKE semantics + `RLS014`
`foreign_table_in_api`), done definition, two-checkpoint interruption
boundary, void condition, judgment rules, and timestamp convention as the
Pair 1r baseline arm
(`../2026-07-06-codex-handoff-003-p1r-baseline/report.md`) — only the
condition differs. Design: `docs/experiment-003-design.md` (including its
Re-registration section).

**Condition (treated)**: the documented ASCS Codex handoff protocol, on
branch `exp-003-p1r-treated` from the same base commit as `p1r-baseline`:
- the ASCS protocol block (content of `examples/codex/AGENTS.md`) appended
  to the target repo's root `AGENTS.md` as a clearly marked scaffolding
  section (the repo's own contributor guide stays intact in both arms)
- `.agent-session/` created from `examples/codex/.agent-session`
  (`handoff.md` plus `state/`)
- the session follows the protocol: read state before working, log decisions
  and failed attempts as they happen (rejected options go to
  `decision-log.md`), write `handoff.md` before the interruption; the
  resumed session starts from `handoff.md`
- the scaffolding (protocol block + `.agent-session/`) is experiment-only:
  removed before any adoption commit, never committed to the target repo's
  main

**Judgment-rule addition (this arm)**: `missed_state_files` also counts any
`.agent-session/` state file that the protocol requires reading on resume
but was not read before acting.

**Known limitation (pre-registered)**: the operator is not blind to
condition, and this arm runs second on the same task as `p1r-baseline`, so
same-task operator learning favors this arm; Pair 2r reverses the order to
compensate (ABBA).

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
