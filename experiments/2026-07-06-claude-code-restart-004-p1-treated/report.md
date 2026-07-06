# Experiment 004 Preregistration - 004-p1-treated

## Task Summary

Experiment 004 measures fresh-session restart recovery for Claude Code on a real target-repo task. This arm is preregistered before any run. No session has started, no target checkout has been created, and no `arm_start` event is recorded.

## Arm Metadata

- Arm: `004-p1-treated`
- Runtime: `claude-code`
- Condition: `treated`
- Pair: `1`
- Order: `2`
- Task: `T-A: ALTER POLICY RENAME tracking + extension_in_public`
- ASCS base: `ae3f4b6`
- Target repo: `supabase-rls-guard`
- Target base commit: `563ad47`
- Interruption: fresh-session restart
- Checkpoint: test-first boundary
- Gate profile: `experiment-004`

## Frozen First Prompt

<!-- FROZEN_FIRST_PROMPT_BEGIN -->
```text
日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

Experiment 004 の作業セッションです。
repo: supabase-rls-guard

制約:
- repo の通常の開発指示を読んで従ってください。
- push / release / issue / PR は作成しないでください。
- 他の AI のレビュー・支援は使わないでください。

Task:
T-A has two slices.

Slice 1: model `ALTER POLICY ... RENAME TO`.
- Add the statement type, parser extraction in both backends, schema-state
  folding, and tests.
- Acceptance assertions: after a rename, an `ALTER POLICY` patch addressed
  to the new name applies; a patch addressed to the old name fails
  conservative; findings report the current name; libpg and regex agree.
- Commit Slice 1 once its tests and the full suite are green.

Slice 2: add `extension_in_public` (target repo ID candidate RLS019).
- After the Slice 1 commit, write the new failing tests first.
- Stop after the Slice 2 tests are present, uncommitted, failing, and no
  Slice 2 implementation files have been edited.
- Do not implement Slice 2 before stopping.

Work order:
- Complete Slice 1 first.
- Commit Slice 1 only after its tests and the full suite are green.
- Then write Slice 2 tests first.
- Run the suite and confirm only the new Slice 2 tests fail.
- Report and wait before editing any Slice 2 implementation file.
```
<!-- FROZEN_FIRST_PROMPT_END -->

## Frozen Resume Prompt

<!-- FROZEN_RESUME_PROMPT_BEGIN -->
```text
日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

前回の fresh session は checkpoint で終了しました。同じタスクを完了してください。

Task:
T-A has two slices.

Slice 1: model `ALTER POLICY ... RENAME TO`.
- Add the statement type, parser extraction in both backends, schema-state
  folding, and tests.
- Acceptance assertions: after a rename, an `ALTER POLICY` patch addressed
  to the new name applies; a patch addressed to the old name fails
  conservative; findings report the current name; libpg and regex agree.
- Commit Slice 1 once its tests and the full suite are green.

Slice 2: add `extension_in_public` (target repo ID candidate RLS019).
- After the Slice 1 commit, write the new failing tests first.
- Stop after the Slice 2 tests are present, uncommitted, failing, and no
  Slice 2 implementation files have been edited.
- Do not implement Slice 2 before stopping.

Done definition:
- Complete the remaining Slice 2 implementation.
- Keep both parser backends consistent where the task requires parity.
- Update the relevant docs and rule count when the task requires it.
- Run the final relevant suite and report the result.
- Do not push, release, create issues, create PRs, or use other AI help.
```
<!-- FROZEN_RESUME_PROMPT_END -->

## Acceptance Assertions

- Slice 1: after a policy rename, an ALTER POLICY patch addressed to the new name applies.
- Slice 1: a patch addressed to the old name fails conservative.
- Slice 1: findings report the current policy name.
- Slice 1: libpg and regex backends agree.
- Slice 2: extension_in_public flags CREATE EXTENSION statements that land in public.
- Slice 2: severity, omitted SCHEMA semantics, parser parity, docs/rules.md, and rule-count bump remain finishing work after the restart boundary.

## Checkpoint Audit Checklist

- A0: each arm uses its own isolated checkout directory before any session starts.
- A1: base commit is 563ad47 in both arms of the pair.
- A2: Slice 1 acceptance assertions hold in both arms.
- A3: at the boundary, the suite fails only the new Slice 2 tests; failing count is recorded.
- A4: git status and diff stat show uncommitted changes confined to test files, except the managed state/scaffold files in the instrumented arm.
- A5: no Slice 2 implementation file is touched.
- A6: number of new Slice 2 test cases is comparable across arms; any material scope difference is recorded.
- A7: the session ended at the first turn where the trigger held.
- A8: no auto-compaction occurred before the boundary.

## missed_checkpoint_items Checklist

- Does not recognize that Slice 1 is already complete and committed.
- Ignores or clobbers the uncommitted Slice 2 failing-test diff.
- Misses the open Slice 2 decisions: implementation location, severity, omitted SCHEMA semantics, parser parity, docs/rules.md, and rule-count bump.
- Reverses Slice 1 rename identity decisions without new evidence.
- Misjudges the checkpoint test pass/fail map.

## Metrics And Gate References

- Layer 1 validity gate: V1-V10 and void conditions decide whether the pair is valid evidence.
- Layer 2 pair comparison: lexicographic tuple (missed_checkpoint_items, human_corrections, recovery_quality with higher better) is applied by scripts/exp004.py pair-verdict.
- Layer 3 public statement gate: scripts/exp004.py claim-check is display-only and applies only after two valid pairs exist.
- resume_time_seconds is reported only and excluded from the comparison tuple, tie-breaks, and headlines.

## Void Condition References

- 1a: Slice 2 implementation edit exists at session end.
- 1b: Slice 2 failing tests were committed before the boundary.
- 2: resume timing event is missing or recorded too late.
- 3: pair checkpoint scope materially differs.
- 4: operator supplement leaks prior progress into the fresh session.
- 5: unregistered auto-compaction occurs before the fixed boundary.
- 6: arm isolation is violated.

## Claim Limits

- No full-stack claim: hooks, compact-plus, session-health, and pxpipe are out of scope.
- No /compact claim: this experiment measures fresh-session restart only.
- No speed headline: resume_time_seconds is reported only.
- No model-superiority, benchmark, production-readiness, or proof claim.

## Events

- See `events.jsonl`. At preregistration, it contains exactly one `preregistration` event.

## Result

<!-- Filled after the arm finishes. -->

## Notes

This file freezes task text, prompts, checkpoint expectations, metrics, gates, and claim limits for this arm. Running the arm starts later through operator action, not through preregistration.
