# Experiments

**What this directory is — and is not.**

The runs recorded here so far are **measurement harness validation runs**:
they verify that `scripts/ascs.py` (init / record / finish / score) and the
experiment file formats work end to end. They are **not** Phase 2
before/after measurements, and they are **not** evidence for the composition
effect of pxpipe + session-health + compact-plus, nor for the Codex handoff
protocol itself.

| Directory | Role |
|---|---|
| `2026-07-06-smoke-test/` | Harness smoke test: exercised init → record → finish → score once against this repository. |
| `2026-07-06-codex-handoff-001/` | Handoff *recording workflow* validation: verified that recovery/state events and metrics can be captured with the harness. The measured task was creating the experiment itself, so the recovery-quality metrics are trivially satisfied. |

Real Phase 2 evidence requires baseline vs treated sessions on real tasks,
with judgment criteria written before the work starts — see
[docs/measurement-plan.md](../docs/measurement-plan.md) and
[docs/measurement-checklist.md](../docs/measurement-checklist.md).
Until such runs exist here, treat every `Score: PASS` in this directory as
"the harness works", not "the stack works".

## Running a real before/after pair (the next experiment)

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
   state-check --note ...`), not retroactively at the end.
4. **Finish each run** with the pre-registered judgment rules applied to the
   session log, then compare the two directories side by side.
5. **Interpretation limit.** n=1 pair is consistency evidence, not causality
   ([docs/measurement-plan.md](../docs/measurement-plan.md) §2). Do not
   aggregate a same-day in-progress session as a final value.
