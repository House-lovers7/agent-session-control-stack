# Experiment Report

## Metadata

- Name: `codex-handoff-003-p2r-treated`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/supabase-rls-guard`
- Created at: `2026-07-06T07:49:07+00:00`

## Task Summary

Experiment 003, **re-registered Pair 2r, treated arm** (runs FIRST in Pair
2r — ABBA reversal; Pair 2r starts only after both Pair 1r arms are
complete). Pair 2's original registration (T2 = `RLS014` single-rule task)
was never run: after Pair 1's void it was marked `redesign-required` (see
`../2026-07-06-codex-handoff-003-p2-treated/events.jsonl`) because a
matched-size single-rule task would likely void the same way. Pre-registered
before any session work; nothing below may change after work begins.
Judgment rules, void condition, recovery_quality rubric (R1–R4), timestamp
convention, and adoption rules are identical to
`../2026-07-06-codex-handoff-003-p1r-baseline/report.md`, with the treated
judgment-rule addition below. Design: `docs/experiment-003-design.md`
(including its Re-registration section).

**Task (T2')** — two parts, both real open gaps in the target repo:

- **Part A — `ALTER POLICY … RENAME TO` identity tracking**: model policy
  renames (self-declared unmodeled in `docs/known-limitations.md`) in both
  parsers and the fold, so that a later `ALTER POLICY <newname>` applies to
  the renamed policy; preserve the conservative behavior where a rename
  target is unknown; tests covering rename → alter chains;
  `docs/known-limitations.md` policy-rename paragraph updated.
- **Part B — new rule `extension_in_public`** (next free id `RLS019`;
  Splinter 0014): flag `CREATE EXTENSION` installed into an API-exposed
  schema (the default `public`). Extension *versions* need a live database;
  extension *schema placement* is statically detectable from migration text
  and is a current blind spot.

**Expected output / done definition**:
- Part A: statement kind for the rename in `src/core/types.ts`; parse
  support in BOTH backends; identity tracking in `src/core/schema-state.ts`;
  tests covering rename → alter chains and the conservative fallback;
  `docs/known-limitations.md` updated
- Part B: new statement kind in `src/core/types.ts`; parse support in BOTH
  backends; fold in `src/core/schema-state.ts`; rule in `src/rules/`;
  registry entry; fire / does-not-fire tests (fires: extension in an exposed
  schema; does not fire: `WITH SCHEMA` into a non-exposed schema,
  allowlisted); `docs/rules.md` and README rule-table rows
- `pnpm typecheck`, `pnpm lint`, `pnpm test` all green
- No claims about ASCS effectiveness anywhere in the deliverable

**Condition (treated)**: the documented ASCS Codex handoff protocol, on
branch `exp-003-p2r-treated`:
- the ASCS protocol block (content of `examples/codex/AGENTS.md`) appended
  to the target repo's root `AGENTS.md` as a clearly marked scaffolding
  section (the repo's own contributor guide stays intact in both arms)
- `.agent-session/` created from `examples/codex/.agent-session`
- the session follows the protocol: read state before working, log decisions
  and failed attempts as they happen (rejected options go to
  `decision-log.md`), write `handoff.md` before the interruption; the
  resumed session starts from `handoff.md`
- the scaffolding is experiment-only: removed before any adoption commit,
  never committed to the target repo's main

**Interruption boundary (pre-registered; two checkpoints)**:
1. **Checkpoint 1**: Part A works against the libpg backend (rename → alter
   chain tests pass), BEFORE starting Part B.
2. **Checkpoint 2**: Part B's rule fires in at least one test against the
   libpg backend, BEFORE Part B's regex parity is complete, before the
   docs/README rows, and before the final all-green run.

Interrupt at the FIRST checkpoint where both have already occurred
in-session: (1) ≥1 visible failure, (2) ≥1 explicitly rejected structuring
option (logged to `decision-log.md` in this arm). If unmet at checkpoint 1,
continue; if still unmet at checkpoint 2, continue to the done definition
and the pair is **void**. Resume in a fresh Codex session starting from
`handoff.md`.

**Judgment-rule addition (this arm)**: `missed_state_files` also counts any
`.agent-session/` state file that the protocol requires reading on resume
but was not read before acting.

**Order and adoption**: Pair 2r order is treated → baseline, on branches
`exp-003-p2r-treated` / `exp-003-p2r-baseline` from the same base commit of
the target repo (which will differ from Pair 1r's base because Pair 1r's
adopted deliverable lands first — recorded, expected). The shipped
deliverable is chosen by human review; the other branch is discarded. n=2
pairs — consistency evidence only, not causality.

## Events

- See `events.jsonl`.

## Result

<!-- Filled by `scripts/ascs.py finish`. -->

## Notes

<!-- One to three lines of qualitative observations. -->
