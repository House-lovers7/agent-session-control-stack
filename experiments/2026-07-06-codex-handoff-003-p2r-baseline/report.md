# Experiment Report

## Metadata

- Name: `codex-handoff-003-p2r-baseline`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T07:49:07+00:00`

## Task Summary

Experiment 003, **re-registered Pair 2r, baseline arm** (runs SECOND in
Pair 2r — ABBA reversal). Pre-registered before any session work; nothing
below may change after work begins. Same task (T2' = `ALTER POLICY … RENAME
TO` identity tracking + `extension_in_public`), done definition,
two-checkpoint interruption boundary (minus the `decision-log.md` clause),
void condition, judgment rules, recovery_quality rubric, timestamp
convention, and adoption rules as the Pair 2r treated arm
(`../2026-07-06-codex-handoff-003-p2r-treated/report.md`), without the
treated-only judgment addition — only the condition differs. Design:
`docs/experiment-003-design.md` (including its Re-registration section).

**Condition (baseline)**: no ASCS handoff protocol block and no
`.agent-session/` in the target repo. The target repo's own contributor
guide (`AGENTS.md`) stays in place in both arms — it is part of the
repository, not the intervention. Plain Codex session on branch
`exp-003-p2r-baseline`, from the same base commit as `p2r-treated`. The
resumed session is given only the target repo and the original task
statement (no state files, no transcript).

**Known limitation (pre-registered)**: the operator is not blind to
condition, and this arm runs second on the same task as `p2r-treated`, so
same-task operator learning favors this arm — symmetric to the learning
advantage the treated arm has in Pair 1r. This symmetry is the point of the
ABBA design.

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
