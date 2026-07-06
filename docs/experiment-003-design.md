# Experiment 003 Design (pre-registered)

Status: **v0.4.0-prep** — measurement design for the next before/after
experiment. This document is written and committed *before* any Experiment
003 session runs. Arm-level task details are pre-registered separately in
each arm's `report.md` at `init` time; this document fixes everything that
must not move after the work starts.

## Goal

Test whether the Codex handoff protocol (`AGENTS.md` + `.agent-session/`)
improves resume behavior on real tasks that are large enough to exercise the
recovery-quality metrics — with the measurement defects of Experiment 002
designed out, not corrected after the fact.

## What Experiment 002 could not answer, and the design response

| 002 defect | 003 design response |
|---|---|
| Resume clocks started at different, rule-violating points per arm | `resume_time_seconds` is **derived by the harness** from `resume-start` → `first-progress-edit` events (`scripts/ascs.py finish` fails without them; a conflicting `--resume-time` is rejected) |
| Notes mixed JST and UTC | All timestamps UTC; `record` warns on clock times in notes without a UTC marker |
| All four recovery-quality metrics were 0–0 (task too small) | Task-size rule below: interruption only after ≥1 visible failure and ≥1 explicitly rejected option |
| Baseline always ran first, on the same task | ABBA counterbalancing across two pairs, different task per pair |
| Target repo was ASCS itself (self-referential, not blind) | Target repo must not be this repository |

## Structure: two pairs, ABBA

| Pair | Task | First arm | Second arm |
|---|---|---|---|
| 1 | T1 | baseline | treated |
| 2 | T2 | **treated** | **baseline** |

- T1 and T2 are real tasks (no synthetic tasks) of matched size in the same
  target repository, chosen before any session starts.
- Within a pair: same base commit, separate branches; the shipped deliverable
  is chosen by human review after both runs; the other branch is discarded.
- Across pairs: the arm order is reversed, and the task differs, so neither
  same-task learning nor a fixed order direction can masquerade as a
  protocol effect.
- Residual (recorded, not controlled away): same operator runs all four
  sessions and is not blind to condition.

## Task-size rule (void-pair condition)

The interruption may only be triggered after, in the pre-interruption
session:

1. at least one approach has **visibly failed** (a failure opportunity for
   `repeated_failures` to bite after resume), and
2. at least one structuring option has been **explicitly rejected** (a
   relapse opportunity for `rejected_option_relapses`).

If a session reaches its done definition before both have occurred, the pair
is **void**: record the void in `events.jsonl`, keep the directory, and
re-register the pair with a larger task. Void pairs are reported, never
silently discarded.

## Metrics

### Score criteria (PASS/FAIL gate — unchanged from 002)

- `missed_state_files` (must be 0)
- `repeated_failures` (must be 0)
- `rejected_option_relapses` (must be 0)
- `human_corrections` (must be ≤ 1)

### Comparison metrics (reported per arm, never gated)

- `resume_time_seconds` — wall clock from the `resume-start` event (recorded
  the moment the first resume prompt is sent) to the `first-progress-edit`
  event (first forward-progress edit that survives into the final
  deliverable). Derived by the harness; never hand-computed. The clock never
  starts at an interruption event or a restart decision. An aborted resume
  attempt is recorded as `resume_attempt_aborted` and superseded by a fresh
  `resume-start`; the last `resume-start` wins, and aborted attempts are
  reported alongside the per-attempt metric.
- `recovery_quality` (0–4) — one point per rubric item, judged against the
  session log with rules fixed before the sessions start:
  - **R1**: the resumed session enumerated the current state (files touched,
    done/remaining work) before its first edit
  - **R2**: it acknowledged the pre-interruption decisions and rejected
    options, with their reasons
  - **R3**: it continued the pre-interruption plan rather than re-planning
    from scratch
  - **R4**: it built on completed work without redoing any of it

`recovery_quality` stays out of the PASS/FAIL gate deliberately: it is a new,
unvalidated rubric, and gating on it before it has discriminated anything
would manufacture failures. Promotion into the gate is a decision for after
Experiment 003, based on whether it discriminates between arms.

### Judgment rules

The five 002 judgment rules (see
`experiments/2026-07-06-codex-handoff-002-baseline/report.md`) carry over
verbatim, with the 002-treated addition (protocol-mandated state files count
toward `missed_state_files` in treated arms) and the R1–R4 rubric above.

## Timezone convention

Every timestamp is UTC (ISO 8601, `+00:00`). Clock times must not be written
into notes in any other timezone; the harness warns when a note contains an
unmarked clock time. Local-time arithmetic is what forced the Experiment 002
correction.

## Recording protocol (both arms, identical)

```bash
python3 scripts/ascs.py init --name codex-handoff-003-p<N>-<arm> --runtime codex --target-repo <target>
# fill report.md Task Summary (task, done definition, condition, judgment rules) BEFORE the session
python3 scripts/ascs.py record --experiment <dir> --event preregistration --note "..."
# ... work ...
python3 scripts/ascs.py record --experiment <dir> --event interruption_reached --note "..."
# fresh session; at the moment the first resume prompt is sent:
python3 scripts/ascs.py record --experiment <dir> --event resume-start --note "..."
# at the first forward-progress edit:
python3 scripts/ascs.py record --experiment <dir> --event first-progress-edit --note "..."
python3 scripts/ascs.py finish --experiment <dir> --missed-state-files N --repeated-failures N \
  --rejected-option-relapses N --human-corrections N --recovery-quality N
```

## Interpretation limits (fixed in advance)

- n=2 pairs is still consistency evidence, not causality
  (docs/measurement-plan.md §2).
- The strongest available claim is directional agreement across both pairs
  under reversed order. Disagreement between pairs is a null result and is
  published as such.
- No percentage improvements will be headlined from this experiment;
  absolute values with limitations travel together.

## Stop conditions

- Void-pair rule above.
- Any harness `FAIL` during `finish` means the recording is fixed and rerun
  from the events — values are never hand-computed around the harness.
- If either pair cannot be completed (e.g., no suitable T2), publish the
  single completed pair as a partial result with the ABBA limitation noted.

## Re-registration (2026-07-06): Pairs 1r and 2r

Everything above this section is the original pre-registration and is left
unchanged. This section is an append-only amendment, written and committed
**before** any re-registered session runs.

**What happened.** Pair 1 ran and was **voided by the task-size rule**: the
baseline session implemented T1 (`RLS012`, a single-rule addition) to its
done definition with zero visible failures and zero explicitly rejected
options — every command exited 0 (operator-verified from the Codex session
log; `void-pair` events in both Pair 1 arms). Pair 2 (T2 = `RLS014`, a
matched-size single-rule task) was never started and is marked
`redesign-required`: it would likely void the same way. The `RLS012`
deliverable was adopted into the target repo's main as product work
(`502db3a`), separately from the experiment record.

**Diagnosis.** A single-rule addition follows an established pattern
(types → parser → fold → rule → tests) and is too smooth to exercise the
recovery-quality metrics. Natural failures and design rejections live in
changes to the *fold semantics* (schema-state), not in pattern-following
rule additions. The original single interruption window (immediately before
regex parity) also closed at exactly the moment it was first evaluated.

**Re-registered task-size criteria** (supersede the original task-size rule
for Pairs 1r/2r; the void-pair rule itself is unchanged):
- the task bundles a **fold-semantics change** (Part A) with a **new rule**
  (Part B), spanning parser(s) / schema-state / registry / docs / tests
- the scale leaves clearly unfinished areas at any interruption point
- failures and rejections must still occur **naturally** — they are never
  instructed; if they do not occur, the pair voids (unchanged)

**Re-registered pairs** (ABBA preserved; old directories kept append-only):

| Pair | Task | First arm | Second arm |
|---|---|---|---|
| 1r | T1' = partial REVOKE subtraction semantics + `RLS014` `foreign_table_in_api` | baseline | treated |
| 2r | T2' = `ALTER POLICY … RENAME TO` identity tracking + `extension_in_public` (`RLS019`) | **treated** | **baseline** |

Both T1' parts and both T2' parts are real open gaps self-declared in the
target repo's `docs/known-limitations.md` (REVOKE conservatism, policy
renames) or statically-detectable Splinter items still missing
(`RLS014`/0017, extension placement/0014). Pair 1r's base commit is the
target repo's main including the adopted `RLS012` (`502db3a`), so no task
overlaps work the operator's runtime has already performed.

**Two-checkpoint interruption boundary** (replaces the single window for
Pairs 1r/2r; full text in each arm's `report.md`):
1. Checkpoint 1 — Part A passes its tests against the libpg backend, before
   Part B starts.
2. Checkpoint 2 — Part B's rule fires against the libpg backend, before
   Part B's regex parity / docs rows / final all-green run.

Interrupt at the first checkpoint where ≥1 visible failure and ≥1 explicitly
rejected option have both already occurred; if still unmet at checkpoint 2,
run to done and record the void. Metrics, judgment rules, the
`recovery_quality` rubric, the UTC convention, and the interpretation limits
above all carry over unchanged.
