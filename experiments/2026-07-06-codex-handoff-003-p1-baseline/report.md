# Experiment Report

## Metadata

- Name: `codex-handoff-003-p1-baseline`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T01:16:26+00:00`

## Task Summary

Experiment 003, **Pair 1, baseline arm** (runs first in Pair 1; Pair 1
completes both arms before Pair 2 starts). Pre-registered before any session
work; nothing below may change after work begins. Design:
`docs/experiment-003-design.md`.

**Task (T1)**: Implement rule `RLS012` `materialized_view_in_api` (Splinter
0016) in supabase-rls-guard: flag `CREATE MATERIALIZED VIEW` in an
API-exposed schema (materialized views are served by the Data API but cannot
carry RLS).

**Expected output / done definition**:
- New statement kind in `src/core/types.ts`; parse support in BOTH backends
  (`src/parser/libpg.ts`, `src/parser/regex.ts`); fold in
  `src/core/schema-state.ts`; rule in `src/rules/objects.ts`; entry in
  `src/rules/registry.ts`
- Fire / does-not-fire tests in `tests/rules.test.ts` (fires: materialized
  view in an exposed schema; does not fire: non-exposed schema, allowlisted,
  dropped materialized view)
- `docs/rules.md` and README rule-table rows
- `pnpm typecheck`, `pnpm lint`, `pnpm test` all green
- No claims about ASCS effectiveness anywhere in the deliverable

**Condition (baseline)**: no ASCS handoff protocol block and no
`.agent-session/` in the target repo. The target repo's own contributor
guide (`AGENTS.md`) stays in place in both arms — it is part of the
repository, not the intervention. Plain Codex session on branch
`exp-003-p1-baseline`.

**Interruption boundary (pre-registered)**: interrupt only when ALL of:
1. at least one approach has visibly failed in-session (e.g., a failing test
   run or an unexpected AST shape),
2. at least one structuring option has been explicitly rejected in-session,
3. the new rule fires in at least one test against the libpg backend.

Interrupt BEFORE regex-backend parity is complete, before the docs/README
rows are added, and before the final all-green run. Resume in a fresh Codex
session given only the target repo and the original task statement.

**Void condition**: if the session reaches the done definition before
conditions 1 and 2 above have both occurred, the pair is **void**: record a
`void-pair` event, keep the directory, and re-register the pair with a
larger task (design doc, task-size rule). Void pairs are reported, never
silently discarded.

**Judgment rules (pre-registered)**:
- `resume_time_seconds`: derived by the harness from the `resume-start`
  event (recorded the moment the first resume prompt is sent) to the
  `first-progress-edit` event (first forward-progress edit that survives
  into the final deliverable). Never hand-computed; the clock never starts
  at an interruption event or a restart decision. An aborted resume attempt
  is recorded as `resume_attempt_aborted` and superseded by a fresh
  `resume-start`.
- `missed_state_files`: pre-interruption artifacts or decisions (files
  created/edited, chosen/rejected options) the resumed session did not
  account for before acting.
- `repeated_failures`: an approach that visibly failed before the
  interruption, re-executed unchanged after resume.
- `rejected_option_relapses`: an option explicitly rejected before the
  interruption, re-proposed after resume without a new stated reason.
- `human_corrections`: human messages needed to redirect the resumed
  session, excluding re-stating the task itself.
- `recovery_quality` (0–4, comparison metric, never gated): one point each,
  judged against the session log —
  - R1: the resumed session enumerated the current state (files touched,
    done/remaining work) before its first edit
  - R2: it acknowledged pre-interruption decisions and rejected options,
    with their reasons
  - R3: it continued the pre-interruption plan rather than re-planning from
    scratch
  - R4: it built on completed work without redoing any of it

**Timestamp convention**: all timestamps UTC (ISO 8601). No non-UTC clock
times in notes (`record` warns).

**Order and adoption**: Pair 1 order is baseline → treated; Pair 2 (T2 =
`RLS014`, separate directories) reverses to treated → baseline (ABBA).
Within the pair, both branches fork from the same base commit of the target
repo; the shipped deliverable is chosen by human review after both runs and
the other branch is discarded. Known limitation (recorded, not controlled):
the same operator runs all sessions and is not blind to condition. n=2 pairs
— consistency evidence only, not causality (docs/measurement-plan.md §2).

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
