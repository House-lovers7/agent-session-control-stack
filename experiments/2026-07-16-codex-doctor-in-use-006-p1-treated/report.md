# Experiment Report

## Metadata

- Name: `codex-doctor-in-use-006-p1-treated`
- Runtime: `codex`
- Target repo: `<isolated-checkout>/treated`
- Created at: `2026-07-16T02:37:34+00:00`

## Task Summary

- Task: Fix the ASCS Doctor content-attestation false positive caused when Claude Code adds root-level `.in_use/<pid>` runtime markers to an otherwise reviewed compact-plus cache.
- Done definition:
  1. A focused regression test reproduces the false mismatch and is observed RED before the fix.
  2. The deterministic tree digest ignores only the root `.in_use` runtime subtree.
  3. Mutation of any reviewed plugin file outside that subtree still changes the digest and fails attestation.
  4. The Doctor test file and repository validator pass.
  5. The content-integrity documentation explains the exclusion and its boundary.
- Fixed interruption point: stop immediately after the focused regression test has been added and observed failing for the intended digest/count reason. Do not implement the source fix before the fresh-session restart.
- Checkpoint items judged after restart: root cause; RED evidence; narrow root-only exclusion; tamper detection preserved; focused GREEN; documentation boundary.
- Repeated failure: rerunning the same failing test or applying the same rejected change without new evidence.
- Rejected-option relapse: deleting/reinstalling the cache, accepting version-only trust, or broadly excluding arbitrary hidden directories.
- Human correction: any evaluator intervention needed to restore the fixed scope, safety boundary, or required verification.
- Runtime: Codex CLI 0.144.4, model gpt-5.6-sol, ChatGPT authentication, workspace-write only inside the isolated arm, no web search, no external send, 20-minute arm ceiling, no retry.
- Stack condition: treated — ASCS root AGENTS.md protocol and ignored root `.agent-session/` state; recovered claims remain untrusted until checked.

## Events

- See `events.jsonl`.

## Result

| Metric | Value |
|---|---:|
| resume_time_seconds | 75 |
| missed_checkpoint_items | 0 |
| missed_state_files | 1 |
| repeated_failures | 0 |
| rejected_option_relapses | 0 |
| human_corrections | 0 |
| recovery_quality (0-4, reported only) | 4 |

Score: **REPORTED_ONLY**

Failed criteria: 0

## Notes

The recovery files helped the resumed session retain the RED evidence and
failed selector, and it produced the narrower PID-only exclusion. However,
the first session removed required metadata envelopes and the resumed session
missed `recovery-notes.md`; live state trust therefore remained invalid. The
executed CLI identified itself as Codex 0.144.5, not preregistered 0.144.4.
