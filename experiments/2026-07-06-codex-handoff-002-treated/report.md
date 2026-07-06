# Experiment Report

## Metadata

- Name: `codex-handoff-002-treated`
- Runtime: `codex`
- Target repo: `/Users/tg/projects/app_development/agent-session-control-stack`
- Created at: `2026-07-05T17:29:10+00:00`

## Task Summary

Experiment 002, **treated arm**. Pre-registered before the session started;
judgment rules below must not be changed after work begins. Same task, same
done definition, same interruption design, and same judgment rules as the
baseline arm (`../2026-07-06-codex-handoff-002-baseline/report.md`) — only
the condition differs.

**Task**: Add a short documentation section explaining when NOT to use Agent
Session Control Stack.

**Expected output / done definition**:
- `docs/when-not-to-use.md` with at least 3 "do not use yet" cases
- `README.md` (and `README.ja.md`) link to it
- No new claims about measured composition effect

**Condition (treated)**: the documented Codex handoff protocol, on branch
`exp-002-treated` from the same base commit as baseline:
- `examples/codex/AGENTS.md` content placed at the repo root as `AGENTS.md`
- `.agent-session/state/` created from `templates/` plus
  `.agent-session/handoff.md`
- The session follows the protocol: read state before working, log decisions
  and failed attempts as they happen, write `handoff.md` before the
  interruption; the resumed session starts from `handoff.md`.
- Root `AGENTS.md` and `.agent-session/` are experiment scaffolding — they
  are removed before any adoption commit and are never committed to main.

**Interruption design**: identical to baseline — interrupt after
`docs/when-not-to-use.md` is drafted and at least one structuring option has
been explicitly rejected (logged to `decision-log.md` in this arm), before
README linking and the final consistency pass. Resume in a fresh Codex
session.

**Judgment rules (pre-registered)**: identical to the baseline arm, with one
addition — `missed_state_files` in this arm also counts any
`.agent-session/` state file that the protocol says must be read on resume
but was not read before acting.

**Order and adoption**: treated runs second. Known limitation: the task is
public in this repo, so the treated session is not blind to the experiment;
recorded as an interpretation caveat, not controlled away. n=1 pair —
consistency evidence only, not causality (docs/measurement-plan.md §2).

## Events

- See `events.jsonl`.

## Result

| Metric | Value |
|---|---:|
| resume_time_seconds | 33 (corrected 2026-07-06; originally published as 92) |
| missed_state_files | 0 |
| repeated_failures | 0 |
| rejected_option_relapses | 0 |
| human_corrections | 0 |

Score: **PASS**

Failed criteria: 0

## Correction (2026-07-06)

The originally published `resume_time_seconds = 92` started the clock at
2026-07-05T18:09:20Z — the post-abort restart decision, 32 seconds *before*
the resume session was created (18:09:52Z) — rather than at the first resume
prompt, violating this arm's own pre-registered judgment rule. The Codex
session log (`rollout-2026-07-06T03-09-52-*.jsonl`) shows the first resume
prompt at 2026-07-05T18:10:19Z; with the recorded first forward-progress edit
at 18:10:52Z this gives **~33 seconds**. See the `correction` event in
`events.jsonl`.

Timezone convention: event `timestamp` fields are UTC; clock times inside
`note` strings are JST (UTC+9).

## Notes

A first resume attempt stalled and was aborted (`resume_attempt_aborted`,
18:09:11Z) before the successful resume; the headline metric measures only
the successful attempt. Total wall clock from interruption (17:53:46Z) to the
successful first edit (18:10:52Z) was ~17 minutes, dominated by the aborted
attempt and human overhead.
