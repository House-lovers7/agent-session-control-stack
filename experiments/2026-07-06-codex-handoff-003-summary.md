# Experiment 003: Closeout — No Resume Comparison Obtained

**Status: closed 2026-07-06.** Experiment 003 produced **no baseline-vs-treated
resume comparison**: no arm reached an interruption, so there is no
`resume_time_seconds`, no `recovery_quality`, no `finish`/`score` output for
any arm. Two consecutive pairs voided under the pre-registered task-size
rule, and the remaining registrations are closed without running. The next
before/after attempt will be a **new experiment number** with a changed
interruption design — not another 003 re-registration.

## What happened, pair by pair

| Pair | Task | Outcome |
|---|---|---|
| 1 | T1 = `RLS012` (single rule) | Baseline ran to its done definition with zero visible failures and zero explicitly rejected options → **void-pair**. Treated never ran (pair-level void). Deliverable adopted as product work (supabase-rls-guard main `502db3a`). |
| 2 | T2 = `RLS014` (single rule, matched size) | Never ran — marked **redesign-required** after Pair 1's void: a matched-size single-rule task would likely void the same way. |
| 1r | T1' = partial REVOKE fold semantics + `RLS014` (cross-cutting bundle, two-checkpoint boundary) | Baseline ran to its done definition with the boundary conditions unmet at **both** pre-registered checkpoints (documented in `checkpoint-observed` events) → **void-pair**. Treated never ran. Deliverable saved as product work on branch `exp-003-p1r-baseline` (`cd8881e`). |
| 2r | T2' = `ALTER POLICY RENAME` identity tracking + `extension_in_public` | Pre-registered, **closed without running** (this closeout). |

All judgments are recorded as append-only events in each arm's
`events.jsonl`; nothing was overwritten.

## The assumption the voids refuted

The 003 interruption boundary required, before any interruption, that **≥1
visible failure and ≥1 explicitly rejected option had occurred naturally**
(never instructed — instructing them would stage the very metrics being
measured). After Pair 1's void the working diagnosis was *task size*: a
fold-semantics change bundled with a new rule should generate natural
failures. Pair 1r refuted that diagnosis. The worker

- probed the parser AST empirically before implementing (no unexpected
  shapes survived to become failures),
- followed established in-repo patterns for the rule work, and
- handled design choices as single-sentence declarations rather than
  deliberated, reasoned rejections.

On a well-structured target repository, the preconditions essentially do not
occur at any tested task size. The strict per-checkpoint judgments were kept
consistent (a design declaration ruled "not a rejection" at checkpoint 1 was
not reinterpreted at checkpoint 2 to save the run) — bending the
pre-registered rule mid-run would have been worse than voiding.

## What worked

The integrity mechanisms behaved as designed: pre-registration froze the
rules before each run, the void rule fired twice instead of being watered
down, operator judgments are auditable events, and both void runs still
produced real product work (`RLS012` on main; the REVOKE semantics +
`RLS014` bundle on a saved branch, adoption pending). The event-derived
resume-timing machinery built for 003 was never exercised — noted here so
that "hardened harness" is not mistaken for "validated harness".

## Design change for the next experiment: fixed checkpoint interruption

The next experiment interrupts **unconditionally at a pre-registered
checkpoint, identical for baseline and treated** — interruption no longer
depends on the worker failing.

- Primary metrics: `missed_state_files`, `recovery_quality` (0–4),
  `human_corrections`, `resume_time_seconds`
- Secondary metrics: `repeated_failures`, `rejected_option_relapses` —
  recorded only if failures/rejections occurred naturally before the
  checkpoint

This is not a return to Experiment 002's defect. 002's flaw was
*unregistered, asymmetric* measurement (ad-hoc interruption, different clock
starts per arm). The fix here is the opposite: a condition-free checkpoint
fixed in advance and shared by both arms, with the clock rules (event-derived
`resume-start` → `first-progress-edit`) unchanged.

## Version note

**v0.4.0 is not tagged.** Experiment 003 produced no comparison, so there is
no measurement release to cut. The next version tag waits for a completed
experiment with results and limitations reflected in the documentation.

## Artifacts

- Arms: `2026-07-06-codex-handoff-003-{p1,p2}-{baseline,treated}/`,
  `2026-07-06-codex-handoff-003-{p1r,p2r}-{baseline,treated}/` (events are
  append-only; reports keep their frozen pre-registrations)
- Design: [docs/experiment-003-design.md](../docs/experiment-003-design.md)
  (original + Re-registration section)
- Product work: supabase-rls-guard `502db3a` (RLS012, adopted to main),
  branch `exp-003-p1r-baseline` @ `cd8881e` (REVOKE semantics + RLS014,
  adoption pending)
