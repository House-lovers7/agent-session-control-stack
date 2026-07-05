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
