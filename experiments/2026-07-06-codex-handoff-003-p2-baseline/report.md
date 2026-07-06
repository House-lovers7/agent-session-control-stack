# Experiment Report

## Metadata

- Name: `codex-handoff-003-p2-baseline`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T01:16:26+00:00`

## Task Summary

Experiment 003, **Pair 2, baseline arm** (runs SECOND in Pair 2 — ABBA
reversal). Pre-registered before any session work; nothing below may change
after work begins. Same task (T2 = `RLS014` `foreign_table_in_api`), done
definition, interruption boundary (minus the `decision-log.md` clause), void
condition, judgment rules, recovery_quality rubric, timestamp convention,
and adoption rules as the Pair 2 treated arm
(`../2026-07-06-codex-handoff-003-p2-treated/report.md`), without the
treated-only judgment addition — only the condition differs. Design:
`docs/experiment-003-design.md`.

**Condition (baseline)**: no ASCS handoff protocol block and no
`.agent-session/` in the target repo. The target repo's own contributor
guide (`AGENTS.md`) stays in place in both arms — it is part of the
repository, not the intervention. Plain Codex session on branch
`exp-003-p2-baseline`, from the same base commit as `p2-treated`. The
resumed session is given only the target repo and the original task
statement (no state files, no transcript).

**Known limitation (pre-registered)**: the operator is not blind to
condition, and this arm runs second on the same task as `p2-treated`, so
same-task operator learning favors this arm — symmetric to the learning
advantage the treated arm had in Pair 1. This symmetry is the point of the
ABBA design.

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
