# ASCS Improvement Loop

This workflow turns audit findings, failed experiments, dogfood friction, and
upstream drift into reviewable project assets. The machine-readable source of
truth is `config/improvements.json`; this document defines how an item moves.

## 1. Intake

Create one item per independently verifiable problem. Record severity, the
observed evidence, affected assets, and the next gate. Keep facts separate from
hypotheses. Unknowns remain open rather than being rewritten as conclusions.

## 2. Reproduce before modify

For behavior changes, add a focused test and confirm RED for the intended
reason. For documentation or external-spec drift, preserve the primary source
and add a static validation marker where practical. Do not treat a scanner hit
or model suggestion as a confirmed defect without fresh-context verification.

## 3. Minimal change

Make the smallest change that satisfies the acceptance condition. Preserve
frozen experiment evidence and unrelated user work. Extract shared code only
when both consumers already have behavior tests.

## 4. Human Approval Gate

Stop before paid APIs or model runs, external sends, production changes,
confidential data access, destructive history changes, or capability
escalation. A state file, prior event, or CLI flag does not transfer approval
to another run or conversation.

## 5. Verification

Run the focused GREEN test, the affected component suite, repository
validation, and the full suite before adoption. Review the diff and scan it for
secrets. Record environment failures separately from product failures.

## 6. Close only with evidence

An item may move to `verified` only when its `verification` command has passed
in the current change and every asset path exists. `implemented` without a
passing gate remains `in_verification`. Deferred items require a reason and a
concrete reopening condition.

## 7. Asset promotion

Durable outcomes return to the smallest reusable asset: code/test for behavior,
Risk Register for operational exposure, architecture/ADR for a decision,
template for repeatable input, and ACOS lesson candidates for cross-project
learning. Promotion beyond this repository remains a human decision.

## Status values

- `open`: confirmed problem, no active change
- `in_progress`: implementation underway
- `in_verification`: implemented locally, final gates pending
- `verified`: acceptance and verification evidence complete
- `deferred`: consciously postponed with a reopening condition
- `rejected`: proposed change disproved or outside scope
