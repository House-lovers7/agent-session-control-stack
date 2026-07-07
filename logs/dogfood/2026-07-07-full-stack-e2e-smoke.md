# Dogfood 0.2 — Full-stack mechanism smoke (real session)

- Date (UTC): 2026-07-07 (session window 14:37–14:52 UTC)
- ASCS commit under test: `2eb1832` (Clarify architecture document positioning)
- Environment: maintainer's machine. session-health 0.3.1 (already installed,
  user scope), compact-plus 1.0.3 (installed for this test via local
  marketplace from upstream `u-ichi/compact-plus`), pxpipe via
  `npx -y pxpipe-proxy` (foreground process, not persisted)
- Test session: disposable cwd `/tmp`, model `claude-fable-5`, routed through
  `ANTHROPIC_BASE_URL=http://127.0.0.1:47821`, session id `9d38be4b-…`

**Scope.** A mechanism smoke test: do all three upstream layers *activate* in
one real Claude Code session, without interfering with each other, as
described in [docs/architecture.md](../../docs/architecture.md)? Run by the
maintainer, single session, one /compact.

**This is not an efficacy measurement.** It does not test whether ASCS
improves anything — no token savings, cost, speed, quality, or composition
*benefit* claim is supported by this log (those belong to numbered
experiments). n=1, unblinded, operator == maintainer.

## What is checked / not checked

| Checked (mechanism activation) | Not checked (out of scope here) |
|---|---|
| pxpipe proxies + images the system slab for an allowlisted model | Any token/cost saving claim |
| pxpipe passes non-allowlisted models through untouched | Recall quality under compression |
| compact-plus PreCompact backs up transcript + writes 10-section state file | Whether recovery *improves* resumed work |
| compact-plus PostCompact → next-prompt recovery injection fires | /compact content quality |
| session-health measures the live segment; stays silent when healthy | hot-path advice efficacy |
| Layers compose without conflict (single compact decider holds) | Full-stack composition effect |

## Procedure and results

### P1 — Repository self-checks — PASS

`python3 -m unittest discover tests` → 70 tests OK. `scripts/ascs.py doctor`
→ all PASS. `scripts/ascs.py measure --experiment 004` → returns the
claim-boundary verdict (composition unmeasured; treated-vs-baseline claims
blocked) as documented. `stack-doctor.sh` → exit 0 against the stack-demo
root, exit 1 with named violations against a root missing state files. All
three demo adapters with env unset → explain + exit 1, nothing executed.

### P2 — session-health live measurement — PASS

Against the maintainer session's transcript, `session_health.py statusline`
printed `req14·51x`; `hook` and `status` stayed silent (healthy — below both
warn gates), matching the documented hot/warn thresholds read from the
installed 0.3.1 source (80/150·min20, 50/100·min10, re-warn every 20).

### P3 — Standalone compact-plus hook chain (no LLM, no billing) — PASS

With synthetic hook JSON and `CLAUDE_PLUGIN_ROOT` set:

- `precompact-transcript-backup.sh` copied a fake transcript to
  `~/.claude/backups/transcripts/<epoch>-<sid>.jsonl` (removed after test).
- `compaction-recovery.sh` wrote the `claude-compacted/<sid>` marker;
  `userpromptsubmit-compaction-recovery.sh` then consumed it (dir empty
  afterwards) and emitted `additionalContext` containing the state-file
  reference and the "treat the compaction summary as hypotheses / original
  files are authoritative" instructions.
- Reminder hook confirmed fail-open: exits immediately when no warn marker
  exists (marker writer lives outside the plugin, as architecture.md §4 says).

### P4 — Real integrated session — PASS

One interactive session through the proxy: read a large doc, `/compact`,
one resume prompt, exit. Evidence from `~/.pxpipe/events.jsonl`, the session
transcript, and the filesystem:

| Observation | Evidence |
|---|---|
| Compression engaged for allowlisted model | 7 requests `model=claude-fable-5, compressed=true`, `image_count=5`, `image_bytes≈499k` per request (static system slab imaged) |
| Per-block gating visible | small request: `compressed=false, reason=below_min_chars (1249 < 2000)`; tool_result blocks passed through with `passthrough_reasons: not_profitable / below_threshold` |
| Allowlist pass-through | `claude-haiku-4-5` probe and the compact-plus `claude -p` (sonnet-5) call: `compressed=false, reason=unsupported_model` |
| Checkpoint fired on /compact | transcript backup `1783435640-9d38be4b….jsonl` (78 KB) in `~/.claude/backups/transcripts/`; state file `claude-compact-state/9d38be4b….md` with exactly the 10 documented sections in order |
| State backend routed through the stack | the state-summary `claude -p --model claude-sonnet-5` request itself appears in the proxy log (passed through) — layers compose without special-casing each other |
| Recovery fired | session transcript contains `compact_boundary` and one `[COMPACTION RECOVERY]` additionalContext injection |
| Single compact decider held | no compact advice from any component other than session-health appeared in the session (compact-plus reminder never fired: no warn-marker writer installed) |
| External noise, not stack failure | 3× HTTP 429 (account rate limit) during the session, retried successfully |

## Verdict: mechanisms work as documented

Every activation claim in architecture.md §3–§5 that this smoke could reach
was observed in a real session. No layer interfered with another; the
"composition by construction" story (single decider, allowlist as the
byte-exact escape hatch, reminder off by absence of the marker writer) held.

## Friction log

1. Upstream README says tool_result imaging kicks in "above ~6k chars", but
   the code default is `minToolResultChars=2000` (TRANSFORM_INFO.md) and the
   observed gate was 2000. architecture.md §3.1 updated to state both.
2. architecture.md §3.2 said all session-health thresholds are env-tunable;
   the ratio gates' minimum request counts (20 hot / 10 warn) are hardcoded.
   §3.2 updated.
3. Upstream (not an ASCS defect): compact-plus `compaction-recovery.sh`
   comment says "80% warning cooldown" while the plugin README documents the
   60% default — stale comment, report-upstream candidate.

## Safety observations

- The zero-billing probe path works: an unauthenticated request through the
  proxy returned the upstream `authentication_error` (real `request_id`),
  proving forwarding without spending tokens.
- Paid steps (`claude -p` state capture, the session itself) were executed by
  the human operator, consistent with the local paid-CLI gate.

## Explicitly not measured

Token/cost savings, recall quality under compression, resume quality, speed,
model comparisons, full-stack composition *benefit*. Nothing in this log
supports an effectiveness claim about ASCS or any upstream tool.
