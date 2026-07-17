# Case study: one real session with the full stack (Dogfood 0.2)

*A readable walkthrough of [logs/dogfood/2026-07-07-full-stack-e2e-smoke.md](../logs/dogfood/2026-07-07-full-stack-e2e-smoke.md). The raw log is the source of truth; this page just tells the story.*

**TL;DR** — On 2026-07-07 the maintainer ran one real Claude Code session with all three layers active at once: pxpipe (compression), session-health (health detection), and compact-plus (checkpoint/recovery). Every mechanism activated as documented, none of them interfered with another, and the single-compact-decider rule held for the whole session.

**What this is not:** an efficacy measurement. n=1, unblinded, operator == maintainer. Nothing here supports a token-saving, speed, quality, or "the stack makes you more productive" claim — those need the numbered experiments. This page only answers: *do the mechanisms actually fire together in a real session, or only on paper?*

## The setup

- Claude Code session in a disposable directory, model `claude-fable-5`, routed through the pxpipe proxy (`ANTHROPIC_BASE_URL=http://127.0.0.1:47821`)
- session-health 0.3.1 (already installed)
- compact-plus 1.0.3 (installed from upstream `u-ichi/compact-plus`, unmodified)
- ASCS commit under test: `2eb1832`

The session itself was deliberately boring: read a large document, run `/compact`, send one resume prompt, exit. Boring is the point — the interesting part is what the layers did around it.

## What happened, layer by layer

**Compression (pxpipe).** The proxy compressed requests for the allowlisted model (7 requests with `compressed=true`; the static system slab was turned into ~499 KB of images per request). Just as important, it *declined* to compress when it shouldn't: a small request was passed through (`below_min_chars`), and requests for non-allowlisted models — including the `claude -p` call that compact-plus makes internally — went through untouched (`unsupported_model`).

**Health detection (session-health).** It measured the live session (`req14·51x` on the statusline) and stayed silent — the session was healthy, below both warn gates. Silence when healthy is the documented behavior, not a failure to run.

**Checkpoint (compact-plus).** When `/compact` fired, compact-plus backed up the full transcript (78 KB) and wrote a state file with exactly the 10 documented sections, in order.

**Recovery (compact-plus).** The next prompt after compaction received one `[COMPACTION RECOVERY]` context injection: a pointer to the state file plus the core recovery rule — *treat the compaction summary as hypotheses; the original files are authoritative.*

**The one composition rule held.** Both session-health and compact-plus are capable of telling the model to compact. The stack designates session-health as the single decider and turns the compact-plus reminder off *by construction* (its warn-marker producer is simply not installed). In the real session, no compact advice came from anything except session-health. No configuration fighting, no double nagging.

One nice cross-layer detail: the `claude -p` request that compact-plus uses to summarize state showed up in the pxpipe proxy log as a pass-through. The layers compose without special-casing each other — each one just does its job and the contracts line up.

## What broke (friction log)

Honest dogfooding finds paper cuts. This run found three, all documentation-level:

1. Upstream pxpipe README says tool_result imaging starts "above ~6k chars"; the actual code default (and observed gate) is 2,000 chars. `architecture.md` now states both.
2. `architecture.md` claimed all session-health thresholds are env-tunable; the ratio gates' minimum request counts are hardcoded. Corrected.
3. A stale comment in upstream compact-plus (says 80% cooldown, README documents 60%) — a report-upstream candidate, not an ASCS defect.

## Reproduce it

```bash
# repo self-checks
python3 -m unittest discover tests
python3 scripts/ascs.py doctor

# install the stack (see README quickstart)
claude plugin marketplace add House-lovers7/agent-session-control-stack
claude plugin install session-health@ascs
claude plugin install compact-plus@ascs
claude plugin install ascs@ascs   # then run /ascs:doctor in a session

# pxpipe is a separate opt-in — read docs/claude-code/pxpipe-safety.md first
npx -y pxpipe-proxy@0.8.0
ANTHROPIC_BASE_URL=http://127.0.0.1:47821 claude
```

Then run a session, `/compact`, and check for yourself: the transcript backup under `~/.claude/backups/transcripts/`, the 10-section state file under `claude-compact-state/`, the recovery injection in the next prompt, and `/ascs:doctor` for the single-decider check.

## Explicitly not measured

Token/cost savings, recall quality under compression, resume quality, speed, model comparisons, and the full-stack composition *benefit*. The claim boundary is machine-checked — see [claim-boundary-model.md](claim-boundary-model.md) and `scripts/ascs.py measure`.
