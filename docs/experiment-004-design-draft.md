# Experiment 004 Design — DRAFT (not yet pre-registered)

Status: **draft for review**. Nothing in this file is frozen. Pre-registration
happens later: this draft becomes binding only when arm directories are
initialized with their `report.md` Task Summaries and `preregistration`
events, and this document's final version is committed before any session
runs. Until then, every section may change.

## Why 004 exists

Experiment 003 closed **without a resume comparison**
(`experiments/2026-07-06-codex-handoff-003-summary.md`): its interruption
boundary required a *naturally occurring* visible failure and an explicitly
rejected option before any interruption, and two consecutive pairs (single
rule task; fold-semantics bundle) reached their done definitions without
either. The refuted assumption is the precondition itself, not the task
size. Experiment 004 removes the precondition: **the interruption is a
pre-registered position in the work, not a reaction to worker behavior.**

## Changes from Experiment 003

| 003 | 004 |
|---|---|
| Interrupt only after ≥1 natural visible failure + ≥1 explicit rejected option | **Fixed checkpoint interruption**: interrupt unconditionally at a pre-registered work position, identical in both arms |
| `repeated_failures` / `rejected_option_relapses` were headline recovery metrics | Demoted to **secondary**: recorded only when failures/rejections occurred naturally before the checkpoint; absence is reported, never counted as evidence |
| Task-size rule: task must be big enough for failures to occur | **Interruption-state rule**: task must produce enough *resumable state* at the checkpoint (multi-file progress + clearly defined remaining work) |
| Void = done reached before the failure/rejection conditions occurred | Void conditions redefined around checkpoint discipline and recording completeness (below) |

Carried over unchanged: event-derived `resume_time_seconds`
(`resume-start` → `first-progress-edit`; hand-computed values rejected), UTC
convention, pre-registration before any session, append-only events, ABBA
counterbalancing across two pairs, same-base-commit-within-pair, adoption of
deliverables by human review separate from the experiment record, n=2 pairs
= consistency evidence only, and no percentage headlines.

## Metrics

### Primary (comparison between arms)

- `missed_state_files` — pre-interruption artifacts/decisions the resumed
  session did not account for before acting (treated arms additionally count
  protocol-mandated `.agent-session/` files not read)
- `recovery_quality` (0–4) — R1–R4 rubric unchanged from 003, one point
  each, judged against the session log
- `human_corrections` — human messages needed to redirect the resumed
  session, excluding re-stating the task
- `resume_time_seconds` — harness-derived, both arms, same clock rules

### Secondary (reported, never required)

- `repeated_failures`, `rejected_option_relapses` — judged with the 003
  rules, but only meaningful if a failure/rejection actually occurred before
  the checkpoint; their absence is stated in the report, not interpreted.

### PASS/FAIL gate

Unchanged from 002/003 for scoring continuity (`missed_state_files` = 0,
`repeated_failures` = 0, `rejected_option_relapses` = 0,
`human_corrections` ≤ 1), with the caveat written into each report that the
two middle criteria pass trivially when no natural failure occurred. The
gate is not the comparison; the primary metrics are. (Open question 3 below
proposes the alternative.)

## Fixed checkpoint — definition

Each task is pre-registered as two named slices, **Slice 1** and **Slice 2**
(as in 003's Part A / Part B). The checkpoint is:

> **Slice 1 passes its new tests against the libpg backend, and Slice 2 has
> not been started.**

At that point the session is stopped **unconditionally** — no conditions,
no operator discretion. The worker's first-session prompt states only the
work order (Slice 1 first, pause before Slice 2); it contains no
failure/rejection language. The resumed session completes the remaining
work: Slice 2, regex parity, docs, final all-green run.

Properties this buys:
- identical, objectively checkable interruption position in both arms
- a well-defined "remaining work" set, so `missed_state_files` and R1–R4
  have real content to bite on
- no dependence on worker behavior → no third void of the 003 kind

## Structure and comparison method

| Pair | Task | First arm | Second arm |
|---|---|---|---|
| 1 | T1'' | baseline | treated |
| 2 | T2'' | **treated** | **baseline** |

- Within a pair: same base commit, separate branches, same fixed checkpoint
  definition; the interruption happens at the same work position in both
  arms.
- Comparison: per-pair, per-metric, baseline vs treated at the same
  checkpoint; across pairs, directional agreement under reversed order is
  the strongest available claim. Disagreement is a null result and is
  published as such.
- Baseline resume: fresh session given only the target repo and the original
  task statement. Treated resume: fresh session starting from `handoff.md`
  per the protocol. (Unchanged from 003.)

## Void conditions (re-registered per pair)

A pair is void if any of:
1. a session **overshoots the checkpoint** (starts Slice 2 before the stop),
2. `resume-start` or `first-progress-edit` was not recorded in an arm,
3. the checkpoint states materially differ between arms (e.g., one arm's
   Slice 1 scope silently grew — judged by the operator against the
   pre-registered slice definitions, decision recorded as an event),
4. any prompt or operator message coached a measured behavior.

Void pairs are recorded with a `void-pair` event, kept, and re-registered —
same rule as 003.

## Open questions to settle BEFORE pre-registration

1. **Task selection.** Candidate: reuse the T2' gaps that 003 never consumed
   (`ALTER POLICY … RENAME TO` identity tracking as Slice 1 +
   `extension_in_public` as Slice 2) for one pair; a second matched
   two-slice task is needed for the other pair. Alternative: pick both tasks
   fresh from the target repo's remaining known-limitations.
2. **Target repo.** supabase-rls-guard again (operator/worker familiarity is
   rising with each run — a drift to record), or a different real repository.
3. **Gate composition.** Keep the 002/003 gate for continuity (current
   draft) vs re-gate on `missed_state_files` = 0 + `human_corrections` ≤ 1
   only, dropping the trivially-passing criteria.
4. **The first-progress-edit prompting amendment.** 003 had resume prompts
   instruct the worker to pause before the first durable edit so the
   operator records `first-progress-edit` (symmetric; adds operator response
   latency). Keep, or switch to operator-timed recording.
5. **Helper tooling.** Adapt `scripts/exp003.py` into an 004 helper:
   `record-interruption` loses its three observation flags (the checkpoint
   is unconditional) and gains a checkpoint-position check; arm definitions,
   prompts, and tests follow the final task choice.
6. **Number of pairs.** Two (ABBA, as drafted) vs more — cost/benefit of
   additional pairs given each pair consumes a real product task.
7. **Checkpoint position.** "Slice 1 complete + Slice 2 not started" (current
   draft; cleanest to verify) vs "Slice 1 complete + Slice 2 partially
   started" (interrupting mid-slice leaves messier, richer state — possibly
   a stronger signal for resume quality, at the cost of a harder-to-verify
   "same position in both arms" claim). Decide before final
   pre-registration.

## Version note

No version tag is attached to this draft. Any release related to Experiment
004 waits until arms have run and results with limitations are reflected in
the documentation.
