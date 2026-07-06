# Experiment 004 Closeout

Date: 2026-07-06

Experiment 004 is stopped here. It does not provide a valid
treated-vs-baseline result, a counterbalanced result, or any productivity,
speed, model-quality, or runtime-quality claim.

## Status

Experiment 004 was started as a Fable 5 / high effort / auto mode gold-run
attempt for Claude Code fresh-session restart arms.

Pair 1 baseline and treated arms were both prepared and started. Both reached
the checkpoint mechanical shape:

- `004-p1-baseline` recorded `interruption_reached` with `failing_count=2`.
- `004-p1-treated` recorded `interruption_reached` with `failing_count=3`.
- The treated arm used the frozen `.agent-session` scaffold and recorded
  matching scaffold tree hashes.

The pair audit was run with `--scope-differs`. This appended
`pair-checkpoint-audit` events with `scope_differs=True` and the note that the
pair should be void condition 3. To preserve append-only audit integrity,
Pair 1 was recorded as `void-pair` condition 3.

Pair 1 must not be used for treated-vs-baseline performance claims. Pair 1
must not proceed to the resume phase.

Pair 2 was not run because continued Fable 5 resource use is not
operationally sustainable for repeated ASCS experiment arms. Experiment 004 is
therefore closed without a recovery comparison.

## Claim Boundary

Allowed statements:

- Experiment 004 validated parts of the ASCS evidence loop: `prepare-arm`,
  `isolation-setup`, checkpoint detection, interruption recording, pair audit,
  and `void-pair` recording.
- Experiment 004 showed that ASCS can restrict claims when a pair becomes
  invalid.
- Experiment 004 produced useful operational lessons for future experiment
  design.

Disallowed statements:

- ASCS improved productivity.
- The treated arm outperformed baseline.
- The baseline arm outperformed treated.
- Fable 5 is better or worse for this workflow.
- Auto mode speed differences prove anything about ASCS.
- Experiment 004 provides a valid counterbalanced result.

## Operational Lessons

- `failing_count` differences alone should not imply `scope_differs`.
- `--scope-differs` is a strong operator judgment that can void a pair.
- Initial implementation time variance under auto mode should be treated as
  runtime variance unless model, approval, or operator conditions differ.
- Future experiments should standardize model, effort, approval mode, and
  runtime conditions before arm start.
- Fable 5 is useful for gold-run exploration, but too expensive/scarce for
  routine repeated ASCS experiments.
- The next experiment should be cut as Experiment 005 using Opus as the
  standard runtime.

## Evidence Notes

This closeout does not rewrite any arm `report.md` file and does not modify
any `events.jsonl` file. It summarizes the append-only events already present
in the Experiment 004 arm directories plus the operator decision to stop
rather than spend further Fable 5 resources on Pair 2.
