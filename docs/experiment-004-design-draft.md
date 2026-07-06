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

- Claude Code's long-session recovery behavior on a real task, across a
  fresh-session restart boundary
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
problem lives: **what a Claude Code session loses across a context
boundary, and whether the ASCS protocol reduces that loss.** Of the two
boundary kinds, 004 measures the **fresh-session restart**; compaction
survival is deferred to follow-up work (see "Interruption method").

## Changes from Experiment 003

| 003 | 004 |
|---|---|
| Runtime under test: Codex | **Claude Code** (Codex comparison out of scope) |
| Interrupt only after ≥1 natural visible failure + ≥1 explicit rejected option | **Fixed checkpoint interruption**: interrupt unconditionally at a pre-registered work position, identical in both arms; no behavioral precondition |
| Interruption = session end + fresh session | Interruption = **fresh-session restart** (fixed; `/compact` was considered and deferred to follow-up work — see "Interruption method") |
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
- at the fixed checkpoint: the session ends and a fresh session is started
  (identical to treated)
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
- after the restart: the fresh session reads the state files and resumes
  from them

Prompts in both arms carry the same task statement and work-order
instructions. No prompt in either arm may name, describe, or hint at any
measured behavior (metric coaching prohibition, unchanged from 003).

## Tasks and target repo — SETTLED (2026-07-06)

Target repo: **supabase-rls-guard** again (open question 2). Operator
familiarity keeps rising with each run and is recorded as a residual;
worker familiarity was reset by the runtime change. Base commit candidate:
`563ad47` (main after the T1' adoption; frozen per pair at
pre-registration). Dynamic-SQL tasks were considered and rejected.

Each task is two slices, sized so that Slice 1 is a completable,
committable unit and Slice 2 supports a real "tests written,
implementation not started" state.

### T-A (Pair 1): rename tracking + `extension_in_public`

**Slice 1 — model `ALTER POLICY … RENAME TO`.** Today the policy stays
tracked under its old name and later patches addressed to the new name are
lost (fails conservative; see the target repo's
`docs/known-limitations.md`). Scope: the statement type
(`src/core/types.ts`), extraction in both parser backends
(`src/parser/libpg.ts` RenameStmt; `src/parser/regex.ts`, which currently
detects and deliberately skips renames), the fold
(`src/core/schema-state.ts`), and tests. Done = the worker's new tests
pass + the full suite green + the acceptance assertions below + a Slice 1
commit. Removing the known-limitations entry is **not** part of Slice 1 —
it belongs to the resumed session's finishing steps.

Acceptance assertion seeds (frozen verbatim at pre-registration):
(a) after a rename, an `ALTER POLICY` clause patch addressed to the new
name applies; (b) a patch addressed to the old name fails conservative,
consistent with existing behavior; (c) findings report the current name;
(d) the libpg and regex backends agree.

**Slice 2 — new rule: extension installed in `public`** (candidate ID
RLS019): flag `CREATE EXTENSION` statements that land the extension in the
`public` schema. Design decisions that remain open at the checkpoint by
construction: implementation location, severity, the semantics of an
omitted `SCHEMA` clause (control-file default vs current schema — requires
an official-docs preflight, deliberately left to the post-boundary work),
regex-backend parity, `docs/rules.md`, and the 18→19 rule-count bump.

### T-B (Pair 2): `CREATE TABLE AS` modeling + one Splinter rule

**Slice 1 — model `CREATE TABLE AS`.** Today the resulting table is not
modeled and column-level rules cannot inspect it (see the target repo's
`docs/known-limitations.md`). Scope: fold the CTAS table into schema state
so table-level rules (e.g. RLS enablement) apply to it, mark its column
list unknown, and make column-level rules skip it without crashing and
without false positives; both parser backends; tests. Acceptance assertion
seeds: (a) a CTAS table without RLS enabled is flagged by the
RLS-enablement rules; (b) column-level rules neither fire nor crash on it;
(c) both backends agree. Done definition and commit discipline as in T-A.

**Slice 2 — one new rule from the official Splinter catalog.** The rule ID
is fixed at pre-registration, after an External Specification Preflight
against the official catalog. Selection criteria (fixed now): (1) the lint
exists in the official Splinter catalog; (2) it is statically detectable
from migration SQL alone (no live catalog needed); (3) comparable in size
to T-A's Slice 2 (new detection + registry + tests + docs; no parser
overhaul); (4) independent of Slice 1's CTAS work, so the partial-start
state stays clean. Unverified candidates (named from memory, pending the
preflight): `no_primary_key`, `unindexed_foreign_keys`, `duplicate_index`.

## Fixed checkpoint — definition

Each task is pre-registered as two named slices, **Slice 1** and **Slice 2**.
The checkpoint position is **mid-slice**, and the stop trigger is
**SETTLED (2026-07-06)** as a **test-first boundary**, identical in
structure for both tasks:

> **Slice 1 is complete and committed (full suite green). Slice 2 exists
> only as its new failing tests — uncommitted, with no implementation
> edit. At the end of the first assistant turn in which that state holds,
> the operator does not reply and ends the session.**

No conditions, no operator discretion about *whether* — only a pre-registered
definition of *where*.

**"Slice 2 partially started" — definition.** All of P1–P4 hold:

- **P1** — at least one new test case for the Slice 2 rule exists in the
  test files and is **uncommitted** (visible in `git diff HEAD`).
- **P2** — running the suite fails **only** the new Slice 2 tests; every
  pre-existing and Slice 1 test is green (operator-run).
- **P3** — zero Slice 2 implementation edits: `git diff HEAD --name-only`
  is confined to test files (plus, in the treated arm, `.agent-session/`
  and the `CLAUDE.md` marker block).
- **P4** — at least one unfinished design decision / open TODO remains. At
  this trigger P4 holds **by construction**: implementation location,
  parser parity, docs, the rule-count bump, and the final green run are
  all untouched. It does not depend on worker behavior — this is the
  direct fix for what voided 003, where the checkpoint required naturally
  occurring events.

**Checkpoint reach conditions (operator-verified before interrupting).**

- **C1** — a Slice 1 commit exists on the arm branch (directly on the
  pair's base commit).
- **C2** — the full suite is green at that commit (operator-run).
- **C3** — P1 holds.
- **C4** — P2 holds.
- **C5** — P3 holds.
- **C6** — the session was ended at the end of the first assistant turn in
  which C1–C5 all held (auditable from the transcript's turn order; the
  operator sends no reply after that turn).

**Staging work order.** Both arms receive the same work-order instructions
(frozen verbatim at pre-registration): complete Slice 1 and commit it when
its tests pass; then write the new rule's tests first, run them, confirm
they fail, and report and wait before implementing. The prompt contains no
failure/rejection language and no mention of the interruption's purpose.
This staging is a work-sequencing instruction, not metric coaching: every
measured behavior belongs to the post-boundary session, and the
instruction names none of them. It also makes the trigger land at a
natural turn boundary, so no session is interrupted mid-edit.

**No adherence prompting in the treated arm.** The operator never tells
the pre-boundary treated session to update its state files before the
interruption. The treatment is the protocol as written; prompting
adherence would have the operator amplifying the treatment. If the treated
arm's state files are stale at the checkpoint, that is a result, not a
protocol violation. (Dogfood 0.1 observed that mid-work state-file updates
needed a nudge — 004 measures the protocol without that nudge.)

**No salvage.** If the session breaks the checkpoint definition — Slice 2
implementation edits exist, or the Slice 2 failing tests were committed —
the pair is void (void conditions 1a/1b). The operator does not repair the
state with `git reset`, `commit --amend`, or `revert`: a repaired tree is
no longer the state the session actually produced, and the uncommitted red
tests are the core of what the resumed session must recover. Under-shoot
is different: if the worker pauses before the trigger (a question, an
early report), the operator may send a work-order-scoped continuation —
pre-boundary operator messages are permitted as long as they coach no
measured (post-boundary) behavior.

**Why mid-slice, not the clean boundary.** "Slice 1 complete + Slice 2 not
started" is easier to verify but leaves almost nothing to recover: the
remaining work is a self-contained, independently startable unit, so a
resumed session can look perfect while having restored nothing. The
protocol's value proposition is restoring **partial progress**: which
approach was adopted, what is half-edited, what has not been touched, which
tests already pass, what was decided but not yet implemented. Mid-slice
interruption is where those signals exist. The cost is a harder
"same position in both arms" claim — mitigated by the concrete test-first
stop trigger above (settled from open question 7), by the checkpoint audit
items below, and by the void condition on materially different checkpoint
states.

The resumed session completes the remaining work: the rest of Slice 2 and
the pre-registered finishing steps (parity/docs/final green run, per the
task's done definition).

## Checkpoint audit — same checkpoint across arms

Recorded per arm at interruption and compared within the pair:

- **A0 (prerequisite — arm isolation)** — each arm runs in its **own
  checkout directory**. Running multiple arms by switching branches inside
  one checkout is **prohibited**. Claude Code project/session context
  (session history, auto-memory, project-scoped state) must not be shared
  between the arms of a pair: both arms run the same task, so any shared
  context is a direct contamination channel. The isolation setup is
  verified and recorded **before** each arm starts; a violation voids the
  pair (void condition 6).
- **A1** — base commit identical across arms (frozen at pre-registration;
  candidate: supabase-rls-guard `563ad47`).
- **A2** — the task's pre-registered Slice 1 acceptance assertions all
  hold in both arms.
- **A3** — suite result at the checkpoint: the failing set is exactly the
  new Slice 2 tests; the count is recorded.
- **A4** — `git status --short -uall` and `git diff --stat`: the
  uncommitted diff is confined to test files. The treated arm's
  `.agent-session/` and `CLAUDE.md` marker block are excluded from the
  between-arm comparison (they are the treatment).
- **A5** — no Slice 2 implementation file touched (both arms).
- **A6** — the number of new Slice 2 test cases is comparable across arms;
  if one arm exceeds twice the other, the operator judges whether the
  scope materially differs (void condition 3) and records the judgment and
  both counts as an event. At n=2 this stays a recorded judgment, not a
  mechanical threshold.
- **A7** — turn-boundary evidence: no pre-boundary turn exists after the
  turn in which the trigger first held.
- **A8** — no auto-compaction before the checkpoint (both arms).

**Derivation of the `missed_checkpoint_items` checklist.** The frozen
per-task checklist maps onto this structure, one category per signal:
Slice 1 already complete and committed (C1/C2); the uncommitted
failing-test diff (C3/A4); the open-decisions list (P4); Slice 1's adopted
design decisions (A2 — e.g. T-A's fail-conservative rename semantics); the
test pass/fail map (A3). Freezing the checklist at pre-registration is
therefore mostly mechanical once this section is fixed.

## Interruption method — FIXED: fresh-session restart

The boundary in Experiment 004 is a **fresh-session restart**, identical in
both arms and both pairs. `/compact` is **not** used as the boundary. The
two were candidates because they measure different things:

- `/compact` — survival of Claude Code's own context compaction: the same
  session continues with a compacted context
- fresh session — cold-restart handoff/recovery: closest to 002/003's
  boundary and to the daily "continue tomorrow" case

**Why fresh session.** With `/compact` as the boundary, the post-boundary
context is a compaction summary **generated by Claude Code itself** — an
artifact that cannot be pre-registered, cannot be held identical between
arms, and varies in quality run to run. The comparison would become
"protocol + summary vs summary alone", with an uncontrolled third
intervention sitting in both arms; at n=2 pairs, its variance can swallow
the protocol effect, and the R1–R4 judgments would be contaminated by
whatever the summary happened to preserve. A fresh-session restart makes the
post-boundary context exactly what the operator provides — fully
pre-registrable, symmetric between arms, and the maximal baseline/treated
contrast (nothing vs protocol files). It also matches the handoff protocol's
primary design case and reuses the 002/003 event machinery unchanged.

**What this defers.** Compaction survival — the Claude Code-specific failure
mode — is **not measured by 004**. It is follow-up work under its own
experiment number, with a design that treats the compaction summary as a
recorded artifact of the measured system rather than an uncontrolled
confounder. 004 first establishes a clean estimate of the protocol effect;
a compaction experiment can then be read against it.

**Auto-compaction contamination.** If Claude Code auto-compacts a session
*before* the fixed checkpoint, that session has crossed an unregistered
context boundary and the pre-registered boundary is no longer the only
context break — this voids the pair (void condition 5). Sessions should be
sized/monitored so the checkpoint is reached first; any auto-compaction
event is recorded regardless of when it occurs.

**Fresh-session context isolation.** The fresh session receives **nothing**
from the pre-boundary session: no conversation log, no summary of it, and no
operator supplement about prior progress ("last time we got this far",
"the approach was X", etc. — all prohibited). The only permitted inputs are:

1. the **pre-registered resume prompt** for that arm (frozen verbatim at
   pre-registration), and
2. the **artifacts inside the target repository working tree** at the
   checkpoint — which, in the treated arm, include `.agent-session/`.

Everything the resumed session knows about prior work must come from those
two channels. An ad-hoc operator supplement — however small — contaminates
the baseline/treated comparison (it is exactly the state transfer the
protocol is being measured against) and voids the pair (void condition 4).

**Arm isolation (audit prerequisite A0).** Isolation applies **between
arms**, not only across the boundary within one arm. The two arms of a
pair run the same task, so any shared Claude Code project or session
context (session history, auto-memory, project-scoped state) is a direct
contamination channel. Each arm therefore runs in its own checkout
directory; running multiple arms by switching branches inside one checkout
is prohibited. The isolation setup is verified and recorded before each
arm starts. A violation voids the pair (void condition 6).

Recording rules: `resume-start` at the moment the first prompt is sent to
the fresh session, `first-progress-edit` at the first forward-progress edit,
both recorded as events, `resume_time_seconds` harness-derived.
Operator-driven throughout — 004 uses **no hooks** for checkpoint recording
or health checks (see "Relation to the full stack").

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

  The per-task checklist derives mechanically from the checkpoint
  definition — see "Checkpoint audit — same checkpoint across arms".
- `recovery_quality` (0–4) — R1–R4 rubric unchanged from 003, one point
  each, judged against the session log
- `human_corrections` — human messages needed to redirect the resumed
  session, excluding re-stating the task
- `resume_time_seconds` — harness-derived, both arms, same clock rules.
  Recorded and reported only: excluded from the comparison tuple, from
  tiebreaking, and from any headline claim (see "Gate design").

### Secondary (reported, never required)

- `missed_state_files` — **treated-only protocol adherence**:
  protocol-mandated `.agent-session/` files the resumed treated session did
  not read before acting. Not a between-arm comparison metric in 004
  (baseline has no such files), so it moves out of the primary set and out
  of any gate that both arms share.
- `repeated_failures`, `rejected_option_relapses` — judged with the 003
  rules, but only meaningful if a failure/rejection actually occurred before
  the checkpoint; their absence is stated in the report, not interpreted.
- `boundary_state_loss_observations` — qualitative, append-only notes of
  concrete state visibly lost across the restart boundary (e.g., a
  constraint stated pre-boundary and contradicted post-boundary), recorded
  as events in both arms. (Named `compaction_state_loss_observations` in an
  earlier draft; renamed because the fixed boundary is a restart, not a
  compaction.)

### Gates — SETTLED (2026-07-06): three layers, no absolute PASS/FAIL

The 002/003-style absolute per-arm PASS/FAIL gate is **retired** for 004
(the earlier candidate — `missed_checkpoint_items` = 0 +
`human_corrections` ≤ 1 — is not adopted). At n=2, an absolute threshold
makes "crossed / did not cross" dominate the reading and invites post-hoc
argument about the threshold itself; 004's question is directional — does
the treated arm recover better than baseline? — not a question about
absolute levels. Gating is split into three layers, all frozen at
pre-registration: a **validity gate** (is the arm/pair evidence at all), a
**recovery comparison rule** (which arm recovered better, correctness
first), and a **public claim gate** (what the two pair verdicts permit
saying). See "Gate design". Absolute metric values are always reported;
they are just not gates.

## Gate design — SETTLED (2026-07-06)

Three layers, applied in order. Layer 1 decides whether an arm/pair is
evidence at all; Layer 2 decides, within each valid pair, which arm
recovered better; Layer 3 decides what may be claimed publicly. A Layer 2
verdict is recorded per valid pair as soon as that pair completes; the
Layer 3 public claim gate is **not applied until two valid pairs exist**.
Void pairs never reach Layer 2 — they are recorded and re-registered.

### Layer 1 — validity gate

An arm fails the validity gate if any item below fails; a pair with a
failing arm is void (recorded with a `void-pair` event and re-registered,
same rule as 003). The items restate the void conditions and the
checkpoint audit as an operational checklist with check timing, so
validity is established **before** outcomes are known.

| # | Item | Checked | Evidence | On failure |
|---|---|---|---|---|
| V1 | A0 arm isolation: own checkout directory, no branch-switch reuse, no shared Claude Code project/session context | before the arm starts | isolation-setup event | pair void (cond. 6) |
| V2 | base commit identical within the pair | before the arm starts | recorded `git rev-parse` | pair void (cond. 3) |
| V3 | checkpoint reached per C1–C6 | at interruption | audit A1–A8 events | pair void |
| V4 | Slice 2 failing tests **uncommitted** | at interruption | `git status` / `git log` | pair void (cond. 1b, no salvage) |
| V5 | Slice 2 implementation untouched | at interruption | `git diff HEAD --name-only` | pair void (cond. 1a, no salvage) |
| V6 | no auto-compaction before the checkpoint | at interruption | session observation record | pair void (cond. 5) |
| V7 | fresh-session context isolation: verbatim-frozen resume prompt, repo artifacts only | at resume | prompt comparison + operator declaration event | pair void (cond. 4) |
| V8 | `resume-start` and `first-progress-edit` recorded | at resume onward | events.jsonl | pair void (cond. 2) |
| V9 | no coaching of measured behavior, on either side of the boundary | whole run | all prompts recorded and compared against pre-registered texts | pair void (cond. 4) |
| V10 | checkpoint states materially equivalent across arms (audit A2–A8) | after interruption, **before resume** | audit events + operator judgment event | pair void (cond. 3) |

V10 is judged before any resume so that no validity decision can be made
with knowledge of an outcome. The timing column gives three stages —
pre-arm (V1–V2), at interruption (V3–V6, V10), at resume (V7–V9) — so
validity is fixed before results exist.

### Layer 2 — recovery comparison rule (correctness first)

Within a valid pair, arms are compared **lexicographically** on the
primary comparison tuple:

1. `missed_checkpoint_items` — lower is better (objective: counted against
   the frozen checklist, both arms)
2. `human_corrections` — lower is better (countable from the transcript)
3. `recovery_quality` (R1–R4, 0–4) — higher is better (rubric-judged;
   placed last because it carries operator judgment)

`resume_time_seconds` is **not** in the tuple, is not a tiebreaker, and
never feeds a headline claim — it is recorded and reported only. This is a
standing consequence of the Experiment 002 correction: 004 measures
whether recovery was *correct*, not whether it was fast.

The first component with a strict difference decides the verdict. No
margins: a one-item difference is an advantage — at one run per arm, a
margin would be false precision; absolute values are published next to
every verdict so readers can weigh them. The tuple's *order* is frozen at
pre-registration precisely to remove post-hoc reordering discretion.

Pair verdicts (recorded per valid pair, as each completes):

| Verdict | Condition |
|---|---|
| treated advantage | treated strictly better at the first differing component |
| tie | all three components equal (regardless of `resume_time_seconds`) |
| baseline advantage | baseline strictly better at the first differing component |
| void / invalid | Layer 1 failed — no comparison is performed |

A tie does not distinguish "both perfect" from "both poor" — the published
report must state the absolute values alongside every verdict. Comparisons
are **within-pair only**: T-A and T-B have different checklist sizes, so
checklist counts are never aggregated or compared across pairs.

### Layer 3 — public claim gate

Applied only when **two valid pairs** exist. Results are published
whichever direction they point (the publication commitment is part of
pre-registration). The complete mapping:

| Pair verdicts (order-free) | Public statement |
|---|---|
| treated + treated | **limited positive signal** — treated advantage in 2/2 pre-registered pairs; n=2 consistency evidence, not proof of effect |
| treated + tie | **below claim threshold** — direction reported descriptively; not called a positive signal |
| tie + tie | **no observed advantage** for the protocol under this design |
| treated + baseline | **inconclusive** — published as a null result |
| baseline + tie | **no observed advantage**, with the baseline-favoring pair stated explicitly |
| baseline + baseline | **negative signal for this protocol design** — published as such and fed back into protocol revision |

**Forbidden claims, regardless of outcome:**

- any full-stack / composition-effect claim (hooks, compact-plus,
  session-health, pxpipe are not measured by 004)
- /compact resilience (only the fresh-session restart boundary is measured)
- production-ready, or any deployment recommendation
- proof of a Claude Code defect (a baseline miss is an observation under
  these conditions, not a runtime-defect finding)
- percentage or speed headlines — anything derived from
  `resume_time_seconds`
- runtime or model comparisons (including Codex)
- generalization beyond this repository, this task class, and this
  protocol version

### Known limits of this gate design

- Ties may be common: Dogfood 0.1 saw near-perfect resume-time adherence,
  and the checklists are small. If both arms hit 0–0–4, the honest verdict
  is "no observed advantage" — accepting a null is a feature of the design
  (the 003 lesson), not a defect.
- `recovery_quality` is judged by an operator who is also the maintainer
  and cannot be blinded; each R1–R4 point therefore requires a recorded
  transcript-referenced rationale, and the metric sits last in the tuple.
- The `human_corrections` boundary (redirect vs permitted work-order
  continuation) must be frozen at pre-registration, and every post-resume
  operator message recorded with a classification — an input to the 004
  helper design (open question 6).

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
  published as such. Each pair's verdict (treated advantage / tie /
  baseline advantage) is produced by the recovery comparison rule in
  "Gate design"; per-metric absolute values are reported alongside.
- Post-boundary session: baseline receives only the task statement plus a
  minimal continuation instruction; treated starts from the protocol's state
  files.

## Void conditions (re-registered per pair)

A pair is void if any of:
1. a session **breaks the checkpoint definition** before the boundary is
   applied —
   - **1a**: any Slice 2 implementation edit exists at session end,
     committed or uncommitted, outside the test files; or
   - **1b**: the Slice 2 failing tests were **committed** before the
     boundary. The uncommitted red tests are the core of the checkpoint
     state; committing them changes what the resumed session has to
     recover.

   Neither case is repaired with `git reset`, `commit --amend`, or
   `revert` — a repaired tree is not the state the session actually
   produced (see "No salvage"). Stopping *short* of the trigger is not
   void; the session continues under the work order.
2. `resume-start` or `first-progress-edit` was not recorded in an arm,
3. the checkpoint states materially differ between arms (e.g., one arm's
   Slice 2 partial progress is substantially larger or touches different
   areas — judged by the operator against the checkpoint audit items
   A1–A8, decision recorded as an event),
4. any prompt or operator message coached a measured behavior (including
   naming the `missed_checkpoint_items` categories to the worker), **or
   supplied the fresh session with any pre-boundary context beyond the
   pre-registered resume prompt and the repo-internal artifacts**
   (fresh-session context isolation — see "Interruption method"),
5. Claude Code auto-compacts a session before the fixed checkpoint is
   reached (an unregistered context boundary preceded the registered one —
   see "Interruption method"),
6. the **arm-isolation prerequisite (A0) is violated**: the pair's arms
   shared a checkout directory (branch switching inside one checkout) or
   shared Claude Code project/session context (see "Interruption method").

Void pairs are recorded with a `void-pair` event, kept, and re-registered —
same rule as 003.

Operationally, these conditions are checked as the validity-gate items
V1–V10 in "Gate design", which adds check timing and evidence but defines
no new conditions.

## Relation to the full stack

ASCS also ships hooks, compact-plus, session-health, and pxpipe. Claude Code
hooks could automate checkpoint recording and health checks at lifecycle
points. **004 deliberately measures none of that**: it isolates the
**protocol effect** (state files + handoff discipline) under operator-driven
recording, because a protocol effect measured through automation would
confound the protocol with the automation. A full-stack composition
experiment is follow-up work with its own design and number.

## Open questions to settle BEFORE pre-registration

1. **Task selection — SETTLED (2026-07-06): T-A and T-B.** T1 = T-A
   (rename tracking + `extension_in_public`), T2 = T-B (`CREATE TABLE AS`
   modeling + one Splinter-catalog rule, ID fixed at pre-registration
   after the official-catalog preflight). Dynamic-SQL tasks rejected. See
   "Tasks and target repo". Numbering kept for traceability.
2. **Target repo — SETTLED (2026-07-06): supabase-rls-guard.** Operator
   familiarity is recorded as a residual; worker familiarity resets with
   the runtime change. Base commit candidate `563ad47`. Numbering kept for
   traceability.
3. **Interruption method — SETTLED (2026-07-06): fresh-session restart.**
   `/compact` vs fresh-session restart was the highest-priority open
   question; it is now fixed to a fresh-session restart in both arms and
   both pairs (rationale in "Interruption method"). Measuring `/compact`
   survival is follow-up work with its own experiment number, not
   additional 004 pairs. Numbering kept for traceability.
4. **Gate composition — SETTLED (2026-07-06): three layers, no absolute
   PASS/FAIL.** The candidate absolute gate (`missed_checkpoint_items` = 0
   + `human_corrections` ≤ 1) is not adopted. Validity gate (V1–V10) →
   per-pair recovery comparison on the lexicographic tuple
   (`missed_checkpoint_items`, `human_corrections`, `recovery_quality`;
   `resume_time_seconds` excluded from the tuple, tiebreaks, and
   headlines) → public claim gate applied only once two valid pairs exist,
   with treated + tie below the claim threshold. Layer 2 verdicts are
   recorded per valid pair as each completes. The tuple order and the
   claim mapping are frozen verbatim at pre-registration. See "Gate
   design". Numbering kept for traceability.
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
7. **Stop-trigger precision — SETTLED (2026-07-06): the test-first
   boundary.** Slice 1 complete and committed; Slice 2 present only as
   uncommitted failing tests; interruption at the end of the first
   assistant turn in which that holds (see "Fixed checkpoint —
   definition", conditions C1–C6). The fallback to "Slice 2 not started"
   is no longer needed: the staging work order makes the trigger reachable
   by construction. Committing the Slice 2 failing tests before the
   boundary is a void condition (1b), with no `reset`/`amend`/`revert`
   salvage. Numbering kept for traceability.
8. **Number of pairs.** Two (ABBA, as drafted) vs more — cost/benefit of
   additional pairs given each pair consumes a real product task.

## Version note

No version tag is attached to this draft. Any release related to Experiment
004 waits until arms have run and results with limitations are reflected in
the documentation.
