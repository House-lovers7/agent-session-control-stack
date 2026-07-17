# Experiments

**What this directory is — and is not.**

Most early runs recorded here are **measurement harness validation runs**:
they verify that `scripts/ascs.py` (init / record / finish / score) and the
experiment file formats work end to end. Experiment 002 is the first manual
n=1 before/after pair for the Codex handoff protocol. None of these runs
validate the full composition effect of pxpipe + session-health + compact-plus.

| Directory | Role |
|---|---|
| `2026-07-06-smoke-test/` | Harness smoke test: exercised init → record → finish → score once against this repository. |
| `2026-07-06-codex-handoff-001/` | Handoff *recording workflow* validation: verified that recovery/state events and metrics can be captured with the harness. The measured task was creating the experiment itself, so the recovery-quality metrics are trivially satisfied. |
| `2026-07-06-codex-handoff-002-summary.md` | Manual n=1 before/after pair for the Codex handoff protocol. **Resume times corrected on 2026-07-06** — the originally published values used asymmetric clock starts; see the summary's Correction notice. |
| `2026-07-06-codex-handoff-002-baseline/` | Baseline arm of Experiment 002 (no ASCS protocol). |
| `2026-07-06-codex-handoff-002-treated/` | Treated arm of Experiment 002 (root `AGENTS.md` + `.agent-session/`). |
| `2026-07-06-codex-handoff-003-p1-baseline/` | Experiment 003, Pair 1 (T1 = `RLS012` in supabase-rls-guard), baseline arm — ran on 2026-07-06 and **voided by the task-size rule** (done definition reached with no visible failure and no rejected option; no resume measured). See its `void-pair` event. The deliverable was adopted as product work (supabase-rls-guard `502db3a`). |
| `2026-07-06-codex-handoff-003-p1-treated/` | Experiment 003, Pair 1, treated arm — never run; **pair-level void** (see `void-pair` event). |
| `2026-07-06-codex-handoff-003-p2-treated/` | Experiment 003, Pair 2 (T2 = `RLS014`), treated arm — never run; **redesign-required** (a matched-size single-rule task would likely void the same way). |
| `2026-07-06-codex-handoff-003-p2-baseline/` | Experiment 003, Pair 2, baseline arm — never run; redesign-required. |
| `2026-07-06-codex-handoff-003-summary.md` | **Experiment 003 closeout** — closed 2026-07-06 with **no resume comparison obtained**: two consecutive voids (Pair 1, Pair 1r) refuted the natural-failure interruption precondition; the next attempt is a new experiment number with fixed-checkpoint interruption. |
| `2026-07-06-codex-handoff-003-p1r-baseline/` | Experiment 003, **re-registered Pair 1r** (T1' = partial REVOKE semantics + `RLS014`, two-checkpoint boundary), baseline arm — ran on 2026-07-06 and **voided**: boundary conditions unmet at both pre-registered checkpoints (see `checkpoint-observed` and `void-pair` events). Deliverable saved as product work on target branch `exp-003-p1r-baseline` (`cd8881e`). |
| `2026-07-06-codex-handoff-003-p1r-treated/` | Experiment 003, Pair 1r, treated arm — never run; **pair-level void**. |
| `2026-07-06-codex-handoff-003-p2r-treated/` | Experiment 003, **re-registered Pair 2r** (T2' = `ALTER POLICY RENAME` identity tracking + `extension_in_public`), treated arm — never run; **closed by the Experiment 003 closeout** (see `experiment-closed` event and the summary). |
| `2026-07-06-codex-handoff-003-p2r-baseline/` | Experiment 003, Pair 2r, baseline arm — never run; closed by the Experiment 003 closeout. |
| `2026-07-06-claude-code-restart-004-closeout.md` | **Experiment 004 closeout** — stopped with no recovery comparison: Pair 1 was voided by `scope_differs=True` / void condition 3 after both arms reached checkpoint shape; Pair 2 was not run because continued Fable 5 resource use was not operationally sustainable. No treated-vs-baseline, productivity, speed, model, or counterbalanced-result claim is allowed. |
| `2026-07-06-claude-code-restart-004-p1-baseline/` | Experiment 004, Pair 1 baseline arm — started and reached checkpoint shape; Pair 1 later voided condition 3. |
| `2026-07-06-claude-code-restart-004-p1-treated/` | Experiment 004, Pair 1 treated arm — started with the frozen `.agent-session` scaffold and reached checkpoint shape; Pair 1 later voided condition 3. |
| `2026-07-06-claude-code-restart-004-p2-treated/` | Experiment 004, Pair 2 treated arm — preregistered only; not run before closeout. |
| `2026-07-06-claude-code-restart-004-p2-baseline/` | Experiment 004, Pair 2 baseline arm — preregistered only; not run before closeout. |
| `2026-07-11-claude-code-restart-005-shared-scaffold/` | **Experiment 005 shared scaffold** — the frozen neutral `.agent-session/` scaffold for 005 treated arms (the 004 scaffold, inherited unchanged). Experiment 005 is **design-registered but not yet pre-registered**: see [docs/experiment-005-design.md](../docs/experiment-005-design.md). No arm directories exist yet — they are created at pre-registration, immediately before the run window, after the paid-runtime cost gate is frozen and approved. |
| `2026-07-16-codex-doctor-in-use-006-summary.md` | Codex fixed-interruption n=1 before/after closeout. Both arms completed, but missing `arm_start` events keep the automated pair verdict incomplete; treated state also failed metadata trust validation. |
| `2026-07-16-codex-doctor-in-use-006-p1-baseline/` | Experiment 006 baseline arm: no root ASCS protocol or state; reported-only metrics recorded. |
| `2026-07-16-codex-doctor-in-use-006-p1-treated/` | Experiment 006 treated arm: root ASCS protocol and state; reported-only metrics recorded, with state-trust failure documented. |

Timezone convention for all `events.jsonl` files: event `timestamp` fields and
any clock times inside new `note` strings are UTC. Historical files remain
unchanged. New events carry `schema_version: 1`; historical events without the
field are read only through the harness's explicit legacy compatibility path.

Stronger Phase 2 evidence requires more baseline vs treated sessions on real
tasks, with judgment criteria written before the work starts — see
[docs/measurement-plan.md](../docs/measurement-plan.md) and
[docs/measurement-checklist.md](../docs/measurement-checklist.md).
Treat every `Score: PASS` in this directory as "the run met its scoring
criteria", not "the stack works generally".

## Running a real before/after pair (the next experiment)

Experiment 003 ([design](../docs/experiment-003-design.md)) was **closed on
2026-07-06 without obtaining a resume comparison** — its
naturally-occurring-failure interruption precondition never fired in two
consecutive attempts (see the
[closeout summary](2026-07-06-codex-handoff-003-summary.md)). Experiment 004
fixed that with an unconditional pre-registered checkpoint but closed
without a recovery comparison (see its closeout above). The next attempt is
**Experiment 005** ([design draft](../docs/experiment-005-design.md)):
Opus as the standard runtime, runtime conditions standardized and recorded
per arm, and a material-difference note required for any `scope_differs`
judgment. The recording rules below (event-derived timing, UTC,
pre-registration before work) carry over unchanged.

One before/after comparison = **two experiment directories** on the same kind
of real task (no synthetic tasks), one per condition:

```bash
python3 scripts/ascs.py init --name codex-handoff-002-baseline --runtime codex --target-repo /path/to/target
python3 scripts/ascs.py init --name codex-handoff-002-treated  --runtime codex --target-repo /path/to/target
```

1. **Pre-register before working.** In each `report.md`, fill in Task Summary
   *before the session starts*: the task, the done definition, the stack
   condition (baseline = no ASCS `AGENTS.md` protocol / no ASCS
   `.agent-session/`; treated = the documented protocol), and the judgment
   rules for each metric (what counts as a repeated failure, a
   rejected-option relapse, a human correction). `finish` warns if Task
   Summary is still a placeholder.
2. **Run the sessions.** Baseline first or treated first — record the order.
   The session must include at least one real interruption boundary (session
   end + resume, or model switch) so `resume_time_seconds` measures something.
3. **Record events as they happen** (`record --event checkpoint|recovery-start|
   state-check --note ...`), not retroactively at the end. In particular,
   record `resume-start` **in both arms** at the moment the first resume
   prompt is sent, and `first-progress-edit` at the first forward-progress
   edit: `finish` derives `resume_time_seconds` from these two events and
   fails without them (hand-computed values are no longer accepted; a
   conflicting `--resume-time` is rejected). The clock never starts at the
   interruption event or at a restart decision — that clock-start asymmetry
   is what forced the Experiment 002 correction. Write any clock time inside
   a note in UTC; `record` warns otherwise.
4. **Finish each run** with the pre-registered judgment rules applied to the
   session log, then compare the two directories side by side.
5. **Interpretation limit.** n=1 pair is consistency evidence, not causality
   ([docs/measurement-plan.md](../docs/measurement-plan.md) §2). Do not
   aggregate a same-day in-progress session as a final value.
