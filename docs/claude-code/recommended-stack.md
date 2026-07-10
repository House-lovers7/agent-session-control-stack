# Recommended Stack for Claude Code

How to run pxpipe, claude-code-session-health, and compact-plus together without them stepping on each other.

## Responsibility split

> - Let **session-health** decide when the session is hot.
> - Let **compact-plus** preserve and restore working state around compaction.
> - Let **pxpipe** reduce bulky input context — but never compress byte-exact values.

One tool decides when to compact the session. One tool protects state across the compact. One tool shrinks what goes over the wire. No tool does another tool's job.

## Who owns which hook

| Surface | session-health | compact-plus | pxpipe |
|---|---|---|---|
| `UserPromptSubmit` | hot-session warning (~60 tokens, at most once per 20 requests) | one-shot recovery injection right after a compact | — |
| `PreCompact` | — | transcript backup + 10-section state file | — |
| `PostCompact` | — (reads the `compact_boundary` transcript record instead) | recovery marker | — |
| `SessionStart` | — | exports the session identifier used by its state lifecycle | — |
| Request path (proxy) | — | — | rewrites bulky content to images |

The only shared surface is `UserPromptSubmit`, and the two injections are small and fire under (nearly) mutually exclusive conditions: session-health warns while a session is hot; compact-plus injects once right after a compact — at which point session-health's live-segment counters have just reset, so it is no longer warning.

## The one real conflict, and how to avoid it

Both tools can tell the model to `/compact`:

- session-health: based on request count and the cacheRead/output ratio
- compact-plus: a reminder when context usage crosses `COMPACT_WARN_THRESHOLD` (default 60%)

Two "compact now" voices with different criteria make the model's behavior unstable. This stack designates **session-health as the single decider**, and turns the compact-plus reminder off **by construction, not configuration**:

> The compact-plus reminder only fires when an *external* statusline script writes a warn marker file. The plugin itself never writes that marker. **If you don't install a marker-producing statusline, the reminder never fires** — while state capture, transcript backup, and recovery injection keep working, because they don't depend on the marker.

No fork, no `hooks.json` edit, no disable flag needed. Just don't install the marker producer.

## Setup order

1. **session-health** — `/plugin marketplace add House-lovers7/claude-code-session-health`, then `/plugin install session-health@house-lovers7`
2. **compact-plus** — install per its README; then set both LLM backends to empty strings (see below) unless you explicitly opt into paid state-file generation
3. **pxpipe** (optional) — read [pxpipe-safety.md](pxpipe-safety.md) first; then `npx -y pxpipe-proxy@0.8.0` and point Claude Code at it with `ANTHROPIC_BASE_URL=http://127.0.0.1:47821`

A ready-made settings snippet is in [examples/claude-code/settings.example.json](../../examples/claude-code/settings.example.json).

## Environment conventions

| Variable | Recommended | Why |
|---|---|---|
| `SESSION_HEALTH_*` (7 knobs) | defaults | thresholds come from the author's measurements; tune only after you have your own numbers |
| `COMPACT_PLUS_PRIMARY_BACKEND` | `""` | the default (`claude -p …`) is a **paid API call on every compact**; keep state-file generation an explicit opt-in |
| `COMPACT_PLUS_FALLBACK_BACKEND` | `""` | same reason (`codex exec` is also metered) |
| `PXPIPE_MODELS` | leave at default | the default allowlist excludes models with high image-misread rates; don't widen it |

With both compact-plus backends empty, you still get transcript backups and recovery markers, but **no LLM-generated 10-section state file**. If you want state capture without paying per compact, keep a manual checkpoint instead — [templates/state-file.md](../../templates/state-file.md) uses the same 10 sections.

## Injection token budget

Everything this stack injects into your prompts: 0 tokens normally; ~60 tokens while hot (at most once per 20 requests); a few hundred tokens once, right after a compact. If you add another injecting plugin, revisit this table.

## Troubleshooting (pxpipe)

**Every request fails right after enabling pxpipe.** The usual cause: `ANTHROPIC_BASE_URL` points at `http://127.0.0.1:47821` but the proxy is not running, so Claude Code cannot reach any model. Fix: start the proxy (`npx -y pxpipe-proxy@0.8.0`) or unset `ANTHROPIC_BASE_URL` for that session. Prevention: never put `ANTHROPIC_BASE_URL` in `settings.json` — use an opt-in alias so a forgotten proxy only affects sessions you explicitly launch through it:

```bash
alias claude-px='ANTHROPIC_BASE_URL=http://127.0.0.1:47821 claude'
```

**The proxy is gone after a reboot.** `npx -y pxpipe-proxy@0.8.0` does not install a service. Start it manually per work session — deliberate at the opt-in stage: a proxy you forgot you daemonized is how byte-exact work ends up on the compressed path.

**Bypass compression without restarting anything.** `PXPIPE_DISABLE=1` is a temporary passthrough (metrics keep recording); `PXPIPE_MODELS=off` turns imaging off while keeping the proxy in place. See [pxpipe-safety.md](pxpipe-safety.md) for when to use which.

**Check the current state.** `lsof -nP -iTCP:47821 -sTCP:LISTEN` shows whether the proxy is up. `/ascs:doctor` (ascs plugin) reports layer status, whether the current session is routed through the proxy, and warns if `ANTHROPIC_BASE_URL` points at a proxy that is not listening.

---

*Facts about upstream behavior were verified against the immutable sources in [upstreams.lock.json](../../config/upstreams.lock.json) on 2026-07-10. Update policy: [upstream-compatibility.md](../upstream-compatibility.md). Design rationale (in Japanese): [architecture.md](../architecture.md), [hook-responsibilities.md](../hook-responsibilities.md).*
