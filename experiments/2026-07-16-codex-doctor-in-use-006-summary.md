# Experiment 006 — Codex fixed-interruption before/after

## Outcome

Both isolated arms completed the same real Doctor bug from the same commit,
with a fresh Codex session before and after the fixed RED interruption. This
is one same-day consistency pair, not causal evidence.

| Metric | Baseline | Treated |
|---|---:|---:|
| missed checkpoint items | 0 | 0 |
| human corrections | 0 | 0 |
| recovery quality (0–4) | 3 | 4 |
| repeated failures | 1 | 0 |
| rejected-option relapses | 0 | 0 |
| missed state files | n/a | 1 |
| event-derived resume time | 63 s | 75 s |

The treated arm retained the failed selector and RED evidence, avoided the
cross-session repeat, and chose a narrower result: only root-level numeric
`.in_use/<pid>` files are excluded; non-PID names, deeper paths, and nested
lookalikes remain attested. Baseline excluded the full root `.in_use` tree.

## Validity limits

- The preregistration named Codex 0.144.4; both executions reported 0.144.5.
  The arms still match each other, but the preregistered runtime label drifted.
- `arm_start` was not recorded when either paid run began. `finish` and `score`
  produced per-arm reported-only metrics, but the automated pair measurement
  correctly classifies the pair as incomplete. No formal treated-wins verdict
  is claimed.
- Treated state content was useful, but its writer removed four required
  `ascs-state-metadata` blocks and left two scaffold placeholders. The resumed
  session read the useful files but did not repair the envelopes or read
  `recovery-notes.md`; state trust validation remained failed.
- Treated's full Doctor test command hit a sandbox loopback-bind restriction.
  Its 18 socket-independent Doctor tests, focused boundary tests, repository
  validator with upstream lock, Python compile, and diff check passed.
  Baseline's 19 Doctor tests and repository validator passed.

## Product decision

Adopt the narrower PID-only exclusion and strengthen the Codex protocol so a
state writer preserves exactly one metadata envelope and validates state after
writing. Hold bootstrap packaging: one incomplete n=1 pair does not satisfy
the three-case low-risk adoption gate and shows a real state-authoring defect.
