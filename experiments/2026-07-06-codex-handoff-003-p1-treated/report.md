# Experiment Report

## Metadata

- Name: `codex-handoff-003-p1-treated`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T01:16:26+00:00`

## Task Summary

Experiment 003, **Pair 1, treated arm** (runs second in Pair 1).
Pre-registered before any session work; nothing below may change after work
begins. Same task (T1 = `RLS012` `materialized_view_in_api`), done
definition, interruption boundary, void condition, judgment rules, and
timestamp convention as the Pair 1 baseline arm
(`../2026-07-06-codex-handoff-003-p1-baseline/report.md`) — only the
condition differs. Design: `docs/experiment-003-design.md`.

**Condition (treated)**: the documented ASCS Codex handoff protocol, on
branch `exp-003-p1-treated` from the same base commit as `p1-baseline`:
- the ASCS protocol block (content of `examples/codex/AGENTS.md`) appended
  to the target repo's root `AGENTS.md` as a clearly marked scaffolding
  section (the repo's own contributor guide stays intact in both arms)
- `.agent-session/state/` created from ASCS `templates/` plus
  `.agent-session/handoff.md`
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
condition, and this arm runs second on the same task as `p1-baseline`, so
same-task operator learning favors this arm; Pair 2 reverses the order to
compensate (ABBA).

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
