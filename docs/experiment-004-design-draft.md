# Experiment 004 Design — DRAFT (not yet pre-registered)

Status: **draft for review**. Nothing in this file is frozen. Pre-registration
happens later: this draft becomes binding only when arm directories are
initialized with their `report.md` Task Summaries and `preregistration`
events, and this document's final version is committed before any session
runs. Until then, every section may change.

## Runtime under test: Claude Code

Experiment 004 tests **Claude Code**, not Codex. This is a deliberate scope
change from Experiments 002/003, stated up front so the experiment cannot
drift into a runtime comparison.

**In scope:**

- Claude Code's compaction / long-session recovery behavior on a real task
- fixed checkpoint interruption, identical in both arms
- the effect of the ASCS state/handoff protocol on resume quality

**Out of scope:**

- any Codex vs Claude Code comparison (003's Codex observations do not
  transfer and are not claimed to)
- model superiority claims of any kind
- generic coding-benchmark claims
- ASCS full-stack performance claims (hooks, compact-plus, session-health,
  pxpipe — see "Relation to the full stack" below)

## Why 004 exists

Two reasons, one inherited and one new.

**Inherited (from 003).** Experiment 003 closed **without a resume
comparison** (`experiments/2026-07-06-codex-handoff-003-summary.md`): its
interruption boundary required a *naturally occurring* visible failure and an
explicitly rejected option before any interruption, and two consecutive
pairs reached their done definitions without either. The refuted assumption
is the precondition itself, not the task size. Experiment 004 removes the
precondition: **the interruption is a pre-registered position in the work,
not a reaction to worker behavior.** No natural-failure or rejected-option
gate is used anywhere in 004.

**New.** ASCS's central claim is about **long-session state control** —
surviving context compaction and session restarts without losing plan,
decisions, and progress. Claude Code is where that claim actually bites: it
compacts long sessions (`/compact`, auto-compaction) and is resumed across
sessions in daily use. 004 therefore measures the protocol where the product
problem lives: **what a Claude Code session loses across a
compaction/restart boundary, and whether the ASCS protocol reduces that
loss.**

## Changes from Experiment 003

| 003 | 004 |
|---|---|
| Runtime under test: Codex | **Claude Code** (Codex comparison out of scope) |
| Interrupt only after ≥1 natural visible failure + ≥1 explicit rejected option | **Fixed checkpoint interruption**: interrupt unconditionally at a pre-registered work position, identical in both arms; no behavioral precondition |
| Interruption = session end + fresh session | Interruption = **compaction or session restart** (which one is an open question; identical in both arms) |
| `missed_state_files` was a primary/gated metric | Moved to **treated-only protocol adherence** (secondary): baseline has no `.agent-session/`, so gating the comparison on it would be structurally unfair |
| No metric for checkpoint-state loss | New primary metric **`missed_checkpoint_items`**, defined against the pre-registered checkpoint state and countable in **both** arms |
| `repeated_failures` / `rejected_option_relapses` were headline recovery metrics | Secondary: recorded only when failures/rejections occurred naturally before the checkpoint; absence is reported, never counted as evidence |
| Task-size rule: task must be big enough for failures to occur | **Interruption-state rule**: the checkpoint must leave rich resumable state — in-progress diff, unfinished design decisions, open TODOs |

Carried over unchanged: event-derived `resume_time_seconds`
(`resume-start` → `first-progress-edit`; hand-computed values rejected), UTC
convention, pre-registration before any session, append-only events, ABBA
counterbalancing across two pairs, same-base-commit-within-pair, adoption of
deliverables by human review separate from the experiment record, n=2 pairs
= consistency evidence only, and no percentage headlines.

## Conditions

### Baseline — standard Claude Code operation

- the target repo's normal instructions (`CLAUDE.md`, README) are allowed
  as-is — baseline is *standard* operation, not a stripped-down one
- no `.agent-session/` directory
- no ASCS handoff/checkpoint files or protocol text
- at the fixed checkpoint: `/compact` or a fresh-session restart (per the
  interruption method chosen at pre-registration; identical to treated)
- resume prompt: the task statement plus a minimal continuation instruction,
  nothing else

### Treated — Claude Code + ASCS protocol

- the ASCS protocol is stated in the target repo's root `CLAUDE.md`
  (appended as a marked block, never replacing existing content — same
  marker discipline as 003's `AGENTS.md` handling)
- `.agent-session/` per the documented protocol:
  `handoff.md`, `state/current-plan.md`, `decision-log.md`,
  `failed-attempts.md`, `checkpoint.md`, `recovery-notes.md`
- the session updates the state files **before** the fixed checkpoint is
  reached (protocol behavior, not operator coaching)
- after `/compact` / restart: the session reads the state files and resumes
  from them

Prompts in both arms carry the same task statement and work-order
instructions. No prompt in either arm may name, describe, or hint at any
measured behavior (metric coaching prohibition, unchanged from 003).

## Fixed checkpoint — definition

Each task is pre-registered as two named slices, **Slice 1** and **Slice 2**.
The first-candidate checkpoint definition is **mid-slice**:

> **Slice 1 is complete (its new tests pass), Slice 2 is partially started,
> and unfinished design decisions / open TODOs / an in-progress diff remain.
> At that point the session is interrupted unconditionally.**

No conditions, no operator discretion about *whether* — only a pre-registered
definition of *where*. The worker's first-session prompt states the work
order (Slice 1, then begin Slice 2) and contains no failure/rejection
language and no mention of the interruption's purpose.

**Why mid-slice, not the clean boundary.** "Slice 1 complete + Slice 2 not
started" is easier to verify but leaves almost nothing to recover: the
remaining work is a self-contained, independently startable unit, so a
resumed session can look perfect while having restored nothing. The
protocol's value proposition is restoring **partial progress**: which
approach was adopted, what is half-edited, what has not been touched, which
tests already pass, what was decided but not yet implemented. Mid-slice
interruption is where those signals exist. The cost is a harder
"same position in both arms" claim — mitigated by pre-registering a concrete
Slice 2 sub-step as the stop trigger (open question 7), and by the void
condition on materially different checkpoint states.

The resumed session completes the remaining work: the rest of Slice 2 and
the pre-registered finishing steps (parity/docs/final green run, per the
task's done definition).

## Interruption method

The boundary is **either** `/compact` **or** a fresh-session restart —
chosen at pre-registration and **identical in both arms and both pairs**
(open question 3). The two measure different things and are **not mixed
within Experiment 004**:

- `/compact` — measures survival of Claude Code's own context compaction:
  the same session continues with a compacted context
- fresh session — measures cold-restart handoff/recovery: closest to
  002/003's boundary and to the daily "continue tomorrow" case

This choice **must be fixed before final pre-registration** — it changes
what the experiment is about, so it cannot be left to per-pair discretion.

Either way, the recording rules are the same: `resume-start` at the moment
the first post-boundary prompt is sent, `first-progress-edit` at the first
forward-progress edit, both recorded as events, `resume_time_seconds`
harness-derived. Operator-driven throughout — 004 uses **no hooks** for
checkpoint recording or health checks (see "Relation to the full stack").

## Metrics

### Primary (comparison between arms)

- `missed_checkpoint_items` — items of the pre-registered checkpoint state
  that the resumed session failed to account for before acting. Countable in
  both arms because it is defined against the **work state**, not against
  protocol files. The item checklist is frozen per-task at pre-registration;
  the categories are:
  - overlooking that Slice 1 is already complete (redoing or re-verifying it
    from scratch)
  - overlooking Slice 2's in-progress diff (ignoring or clobbering it)
  - overlooking an open TODO / unfinished design decision
  - reversing an already-adopted design decision without new cause
  - misjudging which tests already pass
- `recovery_quality` (0–4) — R1–R4 rubric unchanged from 003, one point
  each, judged against the session log
- `human_corrections` — human messages needed to redirect the resumed
  session, excluding re-stating the task
- `resume_time_seconds` — harness-derived, both arms, same clock rules

### Secondary (reported, never required)

- `missed_state_files` — **treated-only protocol adherence**:
  protocol-mandated `.agent-session/` files the resumed treated session did
  not read before acting. Not a between-arm comparison metric in 004
  (baseline has no such files), so it moves out of the primary set and out
  of any gate that both arms share.
- `repeated_failures`, `rejected_option_relapses` — judged with the 003
  rules, but only meaningful if a failure/rejection actually occurred before
  the checkpoint; their absence is stated in the report, not interpreted.
- `compaction_state_loss_observations` — qualitative, append-only notes of
  concrete state visibly lost across the boundary (e.g., a constraint stated
  pre-boundary and contradicted post-boundary), recorded as events in both
  arms.

### PASS/FAIL gate

Open question 4. The 002/003 gate cannot carry over as-is: it gated on
`missed_state_files` = 0, which is now treated-only, and on two metrics that
pass trivially when no natural failure occurred. Current candidate:
`missed_checkpoint_items` = 0 and `human_corrections` ≤ 1, with everything
else reported ungated. The gate is not the comparison; the primary metrics
are.

## Structure and comparison method

| Pair | Task | First arm | Second arm |
|---|---|---|---|
| 1 | T1 | baseline | treated |
| 2 | T2 | **treated** | **baseline** |

- Within a pair: same base commit, separate branches, same fixed checkpoint
  definition, same interruption method; the interruption happens at the same
  pre-registered work position in both arms.
- Comparison: per-pair, per-metric, baseline vs treated at the same
  checkpoint; across pairs, directional agreement under reversed order is
  the strongest available claim. Disagreement is a null result and is
  published as such.
- Post-boundary session: baseline receives only the task statement plus a
  minimal continuation instruction; treated starts from the protocol's state
  files.

## Void conditions (re-registered per pair)

A pair is void if any of:
1. a session **overshoots the checkpoint** (proceeds past the pre-registered
   Slice 2 stop trigger before the boundary is applied),
2. `resume-start` or `first-progress-edit` was not recorded in an arm,
3. the checkpoint states materially differ between arms (e.g., one arm's
   Slice 2 partial progress is substantially larger or touches different
   areas — judged by the operator against the pre-registered slice and
   stop-trigger definitions, decision recorded as an event),
4. any prompt or operator message coached a measured behavior (including
   naming the `missed_checkpoint_items` categories to the worker).

Void pairs are recorded with a `void-pair` event, kept, and re-registered —
same rule as 003.

## Relation to the full stack

ASCS also ships hooks, compact-plus, session-health, and pxpipe. Claude Code
hooks could automate checkpoint recording and health checks at lifecycle
points. **004 deliberately measures none of that**: it isolates the
**protocol effect** (state files + handoff discipline) under operator-driven
recording, because a protocol effect measured through automation would
confound the protocol with the automation. A full-stack composition
experiment is follow-up work with its own design and number.

## Open questions to settle BEFORE pre-registration

1. **Task selection.** Candidate: reuse the T2' gaps that 003 never consumed
   (`ALTER POLICY … RENAME TO` identity tracking as Slice 1 +
   `extension_in_public` as Slice 2) for one pair; a second matched
   two-slice task is needed for the other pair. Alternative: pick both tasks
   fresh from the target repo's remaining known-limitations. Slice 2 must be
   substantial enough that "partially started" is a real state.
2. **Target repo.** supabase-rls-guard again (operator familiarity is rising
   with each run — a drift to record; worker familiarity resets with the
   runtime change), or a different real repository.
3. **Interruption method — the highest-priority open question.**
   `/compact` vs fresh-session restart (see "Interruption method").
   Exactly one is chosen, fixed at pre-registration, and applied identically
   in both arms and both pairs; the two are never mixed within 004.
   Measuring the other method is follow-up work with its own experiment
   number, not additional 004 pairs.
4. **Gate composition.** Adopt the candidate gate
   (`missed_checkpoint_items` = 0 + `human_corrections` ≤ 1) vs report all
   metrics ungated for one experiment before gating a new metric.
5. **The first-progress-edit prompting amendment.** 003 had resume prompts
   instruct the worker to pause before the first durable edit so the
   operator records `first-progress-edit` (symmetric; adds operator response
   latency). Keep, or switch to operator-timed recording — the operator
   watches Claude Code's edits directly, which may make the pause
   unnecessary.
6. **Helper tooling.** Adapt `scripts/exp003.py` into an 004 helper:
   `record-interruption` loses its observation flags (the checkpoint is
   unconditional) and gains a checkpoint-position check; prompts, arm
   definitions, marker handling (`CLAUDE.md` instead of `AGENTS.md`), and
   tests follow the final task and method choices. `ascs.py init` runtime
   label becomes `claude-code`.
7. **Stop-trigger precision for the mid-slice checkpoint.** The
   first-candidate position is "Slice 1 complete + Slice 2 partially
   started"; pre-registration must fix a concrete, auditable Slice 2
   sub-step as the stop trigger (e.g., after the first Slice 2 file edit /
   after Slice 2's failing test is written, before its implementation) so
   the same-position-in-both-arms claim is checkable. If no auditable
   trigger can be defined for the chosen task, fall back to
   "Slice 2 not started" and record the trade-off.
8. **Number of pairs.** Two (ABBA, as drafted) vs more — cost/benefit of
   additional pairs given each pair consumes a real product task, plus one
   more if both interruption methods are to be measured.

## Version note

No version tag is attached to this draft. Any release related to Experiment
004 waits until arms have run and results with limitations are reflected in
the documentation.
