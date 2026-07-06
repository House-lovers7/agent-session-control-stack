# Experiment Report

## Metadata

- Name: `codex-handoff-003-p1r-baseline`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T07:49:07+00:00`

## Task Summary

Experiment 003, **re-registered Pair 1r, baseline arm** (runs first in Pair
1r; Pair 1r completes both arms before Pair 2r starts). Pair 1 (T1 =
`RLS012`, single-rule task) was **voided by the pre-registered task-size
rule** — the session reached its done definition with no visible failure and
no explicitly rejected option (see
`../2026-07-06-codex-handoff-003-p1-baseline/events.jsonl`). This pair
re-registers with a larger, cross-cutting task per that rule. Pre-registered
before any session work; nothing below may change after work begins. Design:
`docs/experiment-003-design.md` (including its Re-registration section).

**Task (T1')** — two parts, both real open gaps self-declared in the target
repo's `docs/known-limitations.md`:

- **Part A — partial REVOKE semantics**: replace the conservative "a grant
  is only cleared when a later `REVOKE` fully covers it" fold with real
  subtraction semantics: per-grantee and per-privilege subtraction,
  `ALL PRIVILEGES` expansion, interop between table-level and schema-wide
  grants, `REVOKE GRANT OPTION FOR` leaving the underlying privilege in
  place, and the conservative direction preserved where the SQL is
  ambiguous. `RLS005` judgments update accordingly.
- **Part B — rule `RLS014` `foreign_table_in_api`** (Splinter 0017): flag
  `CREATE FOREIGN TABLE` in an API-exposed schema (foreign tables are served
  by the Data API but bypass RLS entirely).

**Expected output / done definition**:
- Part A: fold changes in `src/core/schema-state.ts` (and `src/core/types.ts`
  if needed); `RLS005` behavior updated; tests covering partial revoke,
  `ALL PRIVILEGES`, schema-wide interop, and `GRANT OPTION FOR`;
  `docs/known-limitations.md` REVOKE paragraph updated to the new semantics
- Part B: new statement kind in `src/core/types.ts`; parse support in BOTH
  backends (`src/parser/libpg.ts`, `src/parser/regex.ts`); fold in
  `src/core/schema-state.ts`; rule in `src/rules/objects.ts`; entry in
  `src/rules/registry.ts`; fire / does-not-fire tests in
  `tests/rules.test.ts` (fires: foreign table in an exposed schema; does not
  fire: non-exposed schema, allowlisted, dropped foreign table);
  `docs/rules.md` and README rule-table rows
- `pnpm typecheck`, `pnpm lint`, `pnpm test` all green
- No claims about ASCS effectiveness anywhere in the deliverable

**Condition (baseline)**: no ASCS handoff protocol block and no
`.agent-session/` in the target repo. The target repo's own contributor
guide (`AGENTS.md`) stays in place in both arms — it is part of the
repository, not the intervention. Plain Codex session on branch
`exp-003-p1r-baseline`.

**Interruption boundary (pre-registered; two checkpoints — revised after
Pair 1's void, where a single pre-regex-parity window closed before the
conditions could occur)**: the session pauses at two fixed checkpoints:
1. **Checkpoint 1**: Part A works against the libpg backend (its new tests
   pass), BEFORE starting Part B.
2. **Checkpoint 2**: Part B's rule fires in at least one test against the
   libpg backend, BEFORE Part B's regex parity is complete, before the
   docs/README rows, and before the final all-green run.

Interrupt at the FIRST checkpoint where both have already occurred
in-session: (1) at least one approach has visibly failed, and (2) at least
one structuring option has been explicitly rejected. If unmet at checkpoint
1, the session continues; if still unmet at checkpoint 2, the session
continues to the done definition and the pair is **void**. Resume in a fresh
Codex session given only the target repo and the original task statement.

**Void condition**: if the session reaches the done definition with
conditions (1) and (2) never both satisfied, the pair is void: record a
`void-pair` event, keep the directory, and re-register the pair with a
larger task. Void pairs are reported, never silently discarded.

**Judgment rules (pre-registered)**: identical to
`../2026-07-06-codex-handoff-003-p1-baseline/report.md` — event-derived
`resume_time_seconds` (from `resume-start` at the moment the first resume
prompt is sent to `first-progress-edit` at the first forward-progress edit
that survives into the final deliverable; never hand-computed; aborted
attempts superseded by a fresh `resume-start`), `missed_state_files`,
`repeated_failures`, `rejected_option_relapses`, `human_corrections`, and
`recovery_quality` (R1–R4, one point each, comparison metric, never gated).

**Timestamp convention**: all timestamps UTC (ISO 8601). No non-UTC clock
times in notes (`record` warns).

**Order and adoption**: Pair 1r order is baseline → treated; Pair 2r
(T2', separate directories) reverses to treated → baseline (ABBA). Both
Pair 1r branches fork from the same base commit of the target repo — main
including the adopted `RLS012` deliverable
(`502db3a0cd353f6370bc93b46b847248eef0eb10`). Pair 2r's base will differ
because Pair 1r's adopted deliverable lands first (recorded, expected). The
shipped deliverable is chosen by human review after both runs; the other
branch is discarded. Known limitation (recorded, not controlled): the same
operator runs all sessions and is not blind to condition. n=2 pairs —
consistency evidence only, not causality (docs/measurement-plan.md §2).

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
