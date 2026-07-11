# Experiment 005 Design — DRAFT (not yet pre-registered)

Status: **draft for review**. Nothing in this file is frozen. Pre-registration
happens later: this draft becomes binding only when the four arm directories
are initialized with their `report.md` Task Summaries and `preregistration`
events, and this document's final version is committed before any session
runs. Until then, every section may change. The pre-registration procedure is
at the end of this document and is **deliberately not executed yet**.

## Inheritance from Experiment 004

Experiment 005 is the pre-registered follow-up that Experiment 004's closeout
(`experiments/2026-07-06-claude-code-restart-004-closeout.md`) and the 004
design's "Pair count" section call for: a retry under a **new experiment
number** that inherits the prior design **by reference**, with its own
pre-registration and records that never mix with 004's.

**Everything not listed under "Changes from Experiment 004" below is
inherited unchanged from `docs/experiment-004-design-draft.md`**, including:

- runtime under test: Claude Code; fresh-session restart boundary; no hooks
- tasks T-A (rename tracking + `extension_in_public`) and T-B (`CREATE TABLE
  AS` modeling + Splinter 0004 `no_primary_key`), verbatim, including
  acceptance assertion seeds and the T-B Slice 2 checkpoint constraint
- baseline / treated conditions, marker discipline, neutral frozen scaffold
- the fixed checkpoint definition (C1–C6, P1–P4), the staging work order,
  no adherence prompting, no salvage
- the checkpoint audit (A0–A8) — with the A6 refinement below
- fresh-session context isolation and arm isolation (A0)
- resume timing (`resume-start`, `first-progress-edit`, aborted-attempt
  protocol, strict validity, measurement-error statement)
- metrics (primary and secondary) and the three-layer gate design
  (validity gate V1–V10, lexicographic recovery comparison, public claim
  gate), including all forbidden claims
- structure: exactly 2 pairs / 4 arms, ABBA, void pairs never replaced
  within 005, adaptive expansion prohibited
- void conditions 1a/1b and 2–6 — plus new condition 7 below
- the helper contract shape and "what the helper never does"

Experiment 004's arm records, events, and void decisions are 004's; nothing
in 005 reinterprets them.

## Why 005 exists

Experiment 004 closed **without a recovery comparison**:

- **Pair 1** was voided under condition 3 after a `--scope-differs`
  judgment whose recorded basis was only a failing-test-count difference
  (2 vs 3). The closeout's lesson: *"`failing_count` differences alone
  should not imply `scope_differs`."*
- **Pair 2** was never run: sustained Fable 5 use was not operationally
  sustainable for repeated experiment arms.

The closeout directs the follow-up explicitly: cut Experiment 005 with
**Opus as the standard runtime**, and *"standardize model, effort, approval
mode, and runtime conditions before arm start."* 005 exists to run the same
measurement under those two fixes.

## Changes from Experiment 004

| 004 | 005 |
|---|---|
| Runtime conditions chosen per gold-run (Fable 5 / high effort / auto mode), not pre-registered as frozen fields | **Runtime standardization**: model, effort, approval mode, fast-mode state, and CLI version are frozen at pre-registration, recorded per arm at `prepare-arm`, and enforced; violation is new **void condition 7** |
| `verify-pair-checkpoint --scope-differs` took the operator judgment with no required basis | **A6 refinement**: a count difference alone is never a sufficient basis; `--scope-differs` requires a `--note` stating the material difference beyond counts |
| Helper `scripts/exp004.py`; sandbox `~/projects/_sandbox/ascs-exp004`; `exp-004` markers | Helper `scripts/exp005.py`; sandbox `~/projects/_sandbox/ascs-exp005`; `exp-005` markers; arm names `005-*`, branches `exp-005-*` |
| Base commit candidate `563ad47` | Base commit frozen at pre-registration = supabase-rls-guard `main` at freeze time (candidate as of 2026-07-11: `5aa0909`), after the pre-freeze task-stock check below |
| Gate profile `experiment-004` | Gate profile `experiment-005` (identical REPORTED_ONLY semantics; no absolute per-arm gate) |

## Runtime standardization — the 005 primary delta

All four arms run under **identical, pre-registered runtime conditions**.
The frozen fields and their current candidates:

| Field | Candidate (frozen at pre-registration) |
|---|---|
| model | Opus (`claude-opus-4-8`) |
| reasoning effort | high |
| approval mode | auto |
| fast mode | off |
| Claude Code CLI version | the version installed at freeze time (exact string recorded) |

Rules:

- `prepare-arm` takes all five fields as **required arguments** and records
  them in the `isolation-setup` event. The helper refuses a `prepare-arm`
  whose model / effort / approval mode / fast-mode values differ from any
  previously prepared 005 arm.
- The CLI version must be identical **within a pair** (helper-refused
  otherwise). Across pairs, a CLI version difference is recorded and
  reported as a residual, not a void — pairs may run days apart and
  comparisons are within-pair only.
- **No mid-arm switching.** Changing model, effort, approval mode, or
  fast-mode state inside a session (either side of the boundary) voids the
  pair. Machine verification is not available; the operator attests:
  `record-interruption` gains `--runtime-conditions-held` (pre-boundary
  session) and `finish-arm` gains `--runtime-conditions-held`
  (post-boundary session). A missing attestation refuses the command.
- The resumed fresh session uses the same frozen conditions as the
  pre-boundary session.

**Void condition 7 (new)**: the runtime standardization is violated — the
frozen conditions were not used, were changed mid-session, or differ across
arms in a way the rules above prohibit. Recorded with
`record-void-pair --condition 7`.

## A6 / void condition 3 refinement

Inherited A6 text stays: if one arm's new Slice 2 test count exceeds twice
the other's, the operator judges whether the scope materially differs and
records the judgment and both counts. 005 adds the binding rule the 004
closeout demands:

> **A difference in new-test counts or failing-test counts alone is never a
> sufficient basis for `scope_differs=true`.** Crossing the 2× attention
> threshold obliges the operator to look; it does not itself authorize a
> void.

A material difference must be identifiable **beyond counts** — for example:

- one arm's new tests target a different rule, statement class, or
  subsystem than the pre-registered Slice 2 scope;
- one arm's uncommitted diff spans test files for behaviors the other arm
  never touches;
- one arm's checkpoint state fails a different subset of the A2 acceptance
  assertions.

Operationally: `verify-pair-checkpoint --scope-differs` **requires
`--note`** describing the material difference; the helper refuses the flag
without it and prints the count-alone rule. The note is recorded in the
`pair-checkpoint-audit` event of both arms. The judgment itself remains an
operator judgment (recorded, auditable) — 005 deliberately does not replace
it with a mechanical threshold, which at n=2 would itself become an
unvalidated instrument.

## Tasks and base commit

T-A and T-B are inherited verbatim. The 004 Pair 1 run consumed neither
task as product work: as of 2026-07-11, supabase-rls-guard `main`
(`5aa0909`) still lacks rename tracking, CTAS modeling, and both candidate
rules.

**Residual, stated up front**: the operator has now seen T-A worked to the
checkpoint twice (004 Pair 1, both arms). Operator familiarity with both
tasks is higher than in 004 and is recorded as a residual in every 005
report. Worker familiarity is unaffected (fresh sessions, no shared
context — A0).

**Pre-freeze task-stock check** (run at freeze time, recorded in the
pre-registration notes): at the frozen base commit, confirm that

1. `ALTER POLICY … RENAME TO` is still untracked (T-A Slice 1 still real;
   `docs/known-limitations.md` entry present);
2. `CREATE TABLE AS` is still unmodeled (T-B Slice 1 still real);
3. no rule occupying the RLS019/RLS020 ID candidates or implementing
   `extension_in_public` / `no_primary_key` has landed;
4. the T-A/T-B acceptance assertion seeds still type-check against the
   current source layout (file paths in the task text still exist).

If any check fails, the affected task is re-cut **before** pre-registration
(a design change, permitted because nothing is frozen yet).

## Helper: `scripts/exp005.py`

Adapted from `scripts/exp004.py` (the 003→004 precedent). The command
surface and "what the helper never does" are unchanged except:

| Command | Delta from 004 |
|---|---|
| `prepare-arm` | new required args `--model --effort --approval-mode --fast-mode --claude-code-version`; records them in `isolation-setup`; refuses cross-arm mismatch (model/effort/approval/fast: all prepared arms; CLI version: within pair) |
| `record-interruption` | new required attestation `--runtime-conditions-held` |
| `finish-arm` | new required attestation `--runtime-conditions-held`; writes gate profile `experiment-005` |
| `verify-pair-checkpoint` | `--scope-differs` requires `--note <material difference>`; refuses without it and prints the count-alone rule |
| `record-void-pair` | `--condition` accepts `7` |

Constants: sandbox root `~/projects/_sandbox/ascs-exp005/<arm>/supabase-rls-guard`;
`exp-005` CLAUDE.md markers; frozen shared scaffold
`experiments/2026-07-11-claude-code-restart-005-shared-scaffold/.agent-session`;
arm experiment directories `experiments/2026-07-11-claude-code-restart-005-*`
(the date prefix is the design registration date, kept even if freezing
happens later).

`scripts/ascs.py` gains `GATE_PROFILE_EXPERIMENT_005` with semantics
identical to the 004 profile (REPORTED_ONLY, no absolute gate,
`missed_state_files n/a` accepted). Regression tests that re-score the
existing 003 and 004 experiment directories unchanged are mandatory before
any 005 use.

## Pre-registration procedure — to run at freeze time (NOT now)

Recorded here so freezing is a checklist, not a design session. Execute in
order, immediately before the run window (post Max-access decision):

1. Confirm supabase-rls-guard `main`; run the pre-freeze task-stock check;
   freeze the base commit hash.
2. Finalize the runtime standardization fields (model, effort, approval
   mode, fast mode, exact CLI version) as pre-registered values in this
   document.
3. Initialize the four arm directories:
   `python3 scripts/ascs.py init --name claude-code-restart-005-<arm> --runtime claude-code --target-repo <path> --gate-profile experiment-005`.
4. Fill each `report.md` Task Summary before any session: task, done
   definition, stack condition, judgment rules, and the frozen per-task
   `missed_checkpoint_items` checklist (derived mechanically per the 004
   "Checkpoint audit" section).
5. Freeze the first-session and resume prompts verbatim (the helper's
   `print-prompt` output is the frozen text).
6. Record a `preregistration` event in each arm.
7. Commit the final version of this document in the same change.
8. Run `exp005.py doctor` against the target repo and record the result in
   the shared scaffold README.

Until all eight steps are complete, no arm session may start.

## Version note

No version tag is attached to this draft. Any release related to Experiment
005 waits until arms have run and results with limitations are reflected in
the documentation.
