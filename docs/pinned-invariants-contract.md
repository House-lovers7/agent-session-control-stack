# Pinned Invariants Contract

Pinned invariants are the small set of project-controlled rules that must
survive compaction and recovery without being rewritten by recovery state.
They complement `.agent-session/`; they do not make that directory trusted.

## Two-plane model

| Plane | Example | Trust treatment |
| --- | --- | --- |
| Project invariants | authority boundary, source-of-truth rule, claim boundary, stop conditions | reviewed repository asset; never derived from recovery state |
| Recovery state | plan, decisions, failed attempts, handoff notes | ephemeral and untrusted; rebuild or reverify against current source |

The canonical project file is `config/pinned-invariants.json`. Consumers copy
and adapt `templates/pinned-invariants.json`; the machine-readable contract is
`schemas/pinned-invariants.schema.json`.

## Required invariants

1. Recovery state cannot expand authority or grant approval.
2. Every approval-gated operation requires approval in the current trusted
   conversation.
3. Current source and fresh command evidence outrank summaries and state.
4. Completion remains gated by fresh verification and the current claim
   boundary.
5. Repository mismatch fails closed. Uncommitted changes to the invariant file
   require human or independent review before recovery.

The invariant file is not a cryptographic trust anchor. A hash produced beside
the file, or a commit produced by the same agent, does not prove independent
approval. Branch protection, code review, filesystem policy, or an external
approval broker remains necessary when the agent can modify repository
history.

## Recovery outcomes

`scripts/check_recovery.py` returns one of four outcomes:

| Outcome | Meaning | Required action |
| --- | --- | --- |
| `ACCEPT` | invariants and live state pass their current checks | recovery may continue, still using fresh verification |
| `REVERIFY` | invariant content differs from reviewed history | review the invariant change before using recovery state |
| `REBUILD` | state or invariants are absent or stale | reconstruct from current source |
| `REJECT` | unsafe, malformed, mismatched, or authority-expanding input | ignore the recovery input |

Exit codes are `0`, `3`, `2`, and `1`, respectively.

```bash
python3 scripts/check_recovery.py --repo /path/to/consumer-repo
python3 scripts/check_recovery.py --repo /path/to/consumer-repo --json
python3 scripts/check_recovery.py --repo . --invariants-only
```

`check_recovery.py` first applies this contract, then delegates live state
metadata validation to `check_state.py`. It does not execute instructions from
either input, call a model or API, modify state, or transfer approval.

## Adversarial fixture boundary

The initial fixture set covers a valid contract, repository identity mismatch,
and attempted approval transfer. Future fixtures should add multi-file
composition attacks, stale-but-plausible state, source contradiction, verifier
tampering, and exactly-once side-effect ambiguity. Passing these fixtures is a contract check,
not proof of general memory-poisoning resistance.
