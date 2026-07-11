# Measurement Harness

`scripts/ascs.py` is a lightweight Phase 2 measurement helper. It makes manual
experiments easier to run without integrating hooks, starting proxies, or
launching Codex or Claude Code.

## What It Automates

- Repository readiness checks with `doctor`.
- Experiment directory creation under `experiments/`.
  (`doctor` and `init` are anchored to the repository containing the script,
  not to the current working directory, so the commands can be run from
  anywhere.)
- `experiment.json`, `events.jsonl`, and `report.md` creation.
- Manual event recording as JSON Lines.
- Final metric capture.
- PASS / PARTIAL / FAIL scoring for the narrow recovery-quality criteria.
  `score` is read-only; `finish` is the command that writes final metrics and
  updates `report.md`.

`finish` regenerates `report.md`. Only the Task Summary and Notes sections are
preserved from the existing report — and only if they contain real content
rather than the original placeholder comment; anything hand-written in other
sections is discarded. Re-running `finish` overwrites the stored metrics with
the new arguments and refreshes `finished_at` and `scored_at`. If Task Summary
is still empty or a placeholder, `finish` prints a WARN, because judgment
criteria are supposed to be written before outcomes are judged
([measurement-plan.md](measurement-plan.md)).

## Evidence boundary

New `record` entries use event schema version 1:

```json
{"schema_version":1,"timestamp":"2026-07-10T00:00:00+00:00","event":"resume-start","note":"first resume prompt sent"}
```

- `timestamp` must be ISO 8601 UTC; `event` is a bounded safe identifier and
  `note` is a bounded, single-line string.
- Optional `pair_id`, `condition` (`baseline` or `treated`), and
  `transaction_id` fields are schema-validated. Unknown fields and unknown
  schema versions fail closed.
- Historical repository events have no `schema_version`. They remain
  immutable and are accepted only through the measurement code's explicit
  legacy compatibility path; the report discloses the legacy event count.
- `resume-start` → `first-progress-edit` is an explicit state machine.
  `resume-attempt-aborted` discards the active attempt, so a later progress
  event is not trusted until a fresh `resume-start` is recorded.
- A valid comparison requires exactly two arms, exactly one unambiguous
  `baseline` and one `treated`, ordered `arm_start` → `interruption_reached` →
  `pair-verdict` events, and identical non-empty verdict notes in both arms.
  A `p<N>` grouping token alone is not evidence of those semantics.
- Layer markers use exact or delimiter-bounded event tokens. Substrings such
  as `decompression`, `unhealthy`, or `precompactpluspost` do not count.
- Experiment names are resolve-checked under `experiments/`, and all metrics
  reject negative or non-integral values before scoring or persistence.

## What It Does Not Automate

- pxpipe proxy startup.
- Claude Code hook installation or execution.
- compact-plus backend execution.
- Codex wrapper execution.
- Transcript JSONL parsing.
- Dashboards.
- Upstream PRs, issue creation, publish, deploy, or any network action.

## Usage

```bash
python scripts/ascs.py doctor
```

```bash
python scripts/ascs.py init \
  --name codex-handoff-001 \
  --runtime codex \
  --target-repo /path/to/target
```

```bash
python scripts/ascs.py record \
  --experiment experiments/2026-07-06-codex-handoff-001 \
  --event checkpoint \
  --note "decision-log and failed-attempts updated"
```

```bash
python scripts/ascs.py finish \
  --experiment experiments/2026-07-06-codex-handoff-001 \
  --resume-time 180 \
  --missed-state-files 0 \
  --repeated-failures 0 \
  --rejected-option-relapses 0 \
  --human-corrections 1
```

```bash
python scripts/ascs.py score \
  --experiment experiments/2026-07-06-codex-handoff-001
```

## Exit Codes

- `doctor` exits `1` only when a `FAIL` check exists. `PASS` and `WARN`
  findings do not fail the command.
- `init` exits `1` if the experiment name is unsafe, resolves outside
  `experiments/`, or the directory already exists.
- `record`, `finish`, and `score` exit `1` if the requested experiment files are
  missing or malformed.
- `score` prints `PASS`, `PARTIAL`, or `FAIL`, but the command itself exits `0`
  when scoring completes successfully. It does not modify `experiment.json` or
  `report.md`.

## Score Criteria

`score` uses the following checks:

- `missed_state_files == 0`
- `repeated_failures == 0`
- `rejected_option_relapses == 0`
- `human_corrections <= 1`

Result:

- `PASS`: all criteria pass.
- `PARTIAL`: one or two criteria miss.
- `FAIL`: three or more criteria miss.

## Relationship To Withdrawal Criteria

The harness does not prove causality. It only makes the manual evidence in
`docs/measurement-plan.md` easier to collect consistently. If repeated
experiments show no improvement in recovery quality, rejected-option relapse,
or repeated-failure avoidance, the integration should not proceed to heavier
tooling such as generators, doctor automation beyond this script, dashboards,
or upstream proposals.
