# Experiment Report

## Metadata

- Name: `codex-handoff-003-p2-treated`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T01:16:26+00:00`

## Task Summary

Experiment 003, **Pair 2, treated arm** (runs FIRST in Pair 2 — ABBA
reversal; Pair 2 starts only after both Pair 1 arms are complete).
Pre-registered before any session work; nothing below may change after work
begins. Judgment rules, void condition, recovery_quality rubric (R1–R4),
timestamp convention, and adoption rules are identical to
`../2026-07-06-codex-handoff-003-p1-baseline/report.md`, with the treated
judgment-rule addition below. Design: `docs/experiment-003-design.md`.

**Task (T2)**: Implement rule `RLS014` `foreign_table_in_api` (Splinter
0017) in supabase-rls-guard: flag `CREATE FOREIGN TABLE` in an API-exposed
schema (foreign tables are served by the Data API but bypass RLS entirely).

**Expected output / done definition**:
- New statement kind in `src/core/types.ts`; parse support in BOTH backends
  (`src/parser/libpg.ts`, `src/parser/regex.ts`); fold in
  `src/core/schema-state.ts`; rule in `src/rules/objects.ts`; entry in
  `src/rules/registry.ts`
- Fire / does-not-fire tests in `tests/rules.test.ts` (fires: foreign table
  in an exposed schema; does not fire: non-exposed schema, allowlisted,
  dropped foreign table)
- `docs/rules.md` and README rule-table rows
- `pnpm typecheck`, `pnpm lint`, `pnpm test` all green
- No claims about ASCS effectiveness anywhere in the deliverable

**Condition (treated)**: the documented ASCS Codex handoff protocol, on
branch `exp-003-p2-treated`:
- the ASCS protocol block (content of `examples/codex/AGENTS.md`) appended
  to the target repo's root `AGENTS.md` as a clearly marked scaffolding
  section (the repo's own contributor guide stays intact in both arms)
- `.agent-session/state/` created from ASCS `templates/` plus
  `.agent-session/handoff.md`
- the session follows the protocol: read state before working, log decisions
  and failed attempts as they happen (rejected options go to
  `decision-log.md`), write `handoff.md` before the interruption; the
  resumed session starts from `handoff.md`
- the scaffolding is experiment-only: removed before any adoption commit,
  never committed to the target repo's main

**Interruption boundary (pre-registered)**: interrupt only when ALL of:
1. at least one approach has visibly failed in-session,
2. at least one structuring option has been explicitly rejected in-session
   (logged to `decision-log.md` in this arm),
3. the new rule fires in at least one test against the libpg backend.

Interrupt BEFORE regex-backend parity is complete, before the docs/README
rows are added, and before the final all-green run. Resume in a fresh Codex
session starting from `handoff.md`.

**Judgment-rule addition (this arm)**: `missed_state_files` also counts any
`.agent-session/` state file that the protocol requires reading on resume
but was not read before acting.

**Order and adoption**: Pair 2 order is treated → baseline, on branches
`exp-003-p2-treated` / `exp-003-p2-baseline` from the same base commit of
the target repo (which will differ from Pair 1's base commit because Pair
1's adopted deliverable lands first — recorded, expected). The shipped
deliverable is chosen by human review; the other branch is discarded. n=2
pairs — consistency evidence only, not causality.

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
