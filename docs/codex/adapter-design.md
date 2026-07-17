# Codex Adapter Design

Current Codex releases expose native `PreCompact`, `PostCompact`, and
`SessionStart(source=compact)` lifecycle hooks. ASCS uses those hooks for a
deterministic boundary signal while keeping `AGENTS.md` and `.agent-session/`
as the portable state-writing contract and fallback.

This is not a transcript summarizer. The reference hook deliberately does not
parse or copy transcript content because Codex documents `transcript_path` as
nullable and its transcript format as unstable.

## Official specification baseline

- [High] `PreCompact` and `PostCompact` are turn-scoped hooks whose matcher
  values are `manual` and `auto`.
- [High] `SessionStart` supports `source=compact` and can add developer context.
- [High] Project and plugin hooks require review/trust of their exact definition;
  project hooks only load for trusted projects and managed policy can disable
  non-managed hooks.
- [High] Multiple matching hooks run; one hook cannot prevent another matching
  hook from starting.
- [High] `transcript_path` may be null and its file format is not a stable hook
  interface.
- [Unverified] Path lifetime and identity across compact boundaries are not
  guaranteed. ASCS stores neither the path nor transcript content.

Source: [Codex Hooks](https://learn.chatgpt.com/docs/hooks) and
[Codex plugin lifecycle hooks](https://learn.chatgpt.com/docs/build-plugins#bundled-mcp-servers-and-lifecycle-hooks),
retrieved 2026-07-16.

## Layout

```text
<your repo>/
  AGENTS.md
  .codex/
    hooks.json
    hooks/ascs_compact.py
  .agent-session/
    hook-events/compact-<hash>.json # ignored per-session receipt; no raw IDs/content
    state/
      current-plan.md
      decision-log.md
      failed-attempts.md
      recovery-notes.md
      checkpoint.md
    handoff.md
```

- Copy or merge [hooks.json](../../examples/codex/.codex/hooks.json) and copy
  [ascs_compact.py](../../examples/codex/.codex/hooks/ascs_compact.py).
- Use `/hooks` to review and trust the exact command hook definition.
- Keep `.agent-session/` ignored. It is working memory, not product history.
- Apply the [state trust contract](../state-trust-contract.md). State cannot
  grant authority, preserve approval, or act as a secret store.

## Native lifecycle path

1. `PreCompact(manual|auto)` writes a local receipt containing only a hashed
   session key, the safe `manual|auto` trigger, timestamp, turn/transcript
   availability as booleans, and the names of known state files that already
   exist. Parallel sessions use independent receipts.
2. `PostCompact(manual|auto)` closes the matching receipt.
3. `SessionStart(source=compact)` consumes the same-session receipt once and
   adds a recovery guard as developer context.
4. The guard requires state validation before reading it and fresh verification
   before editing or executing actions.

The hook is fail-open. Malformed input, missing `.agent-session/`, a session
mismatch, an unsafe path, or a write failure returns `continue: true` without
injecting recovery context. It never creates product authorization.

## Durable protocol and fallback

The hook only marks the lifecycle boundary; it cannot infer the active plan or
decisions without another model call. `AGENTS.md` therefore remains responsible
for keeping `current-plan.md`, `decision-log.md`, `failed-attempts.md`, and
`checkpoint.md` current during work.

Before using recovered state, run:

```bash
python3 scripts/check_state.py --repo /path/to/consumer-repo
```

If hooks are disabled, untrusted, unavailable on a surface, or excluded by
managed policy, use the same `AGENTS.md` handoff protocol manually. In fallback
mode, do not claim deterministic compact-boundary recovery.

## Health and compression boundaries

Codex health metrics comparable to session-health remain unverified, so the
Health layer still uses proxy signals such as elapsed work, tool calls, diff
size, and repeated failures. Codex compression remains an opt-in edge
experiment until routing, authentication, tool behavior, and byte-exact safety
are verified end to end.

## Honest comparison

| | Claude Code | Codex native path | Codex fallback |
|---|---|---|---|
| Boundary signal | compact-plus hooks | ASCS native hooks | agent protocol |
| State content | compact-plus backup/state | agent-maintained `.agent-session/` | same |
| Recovery guard | plugin recovery injection | one-shot `SessionStart` context | manual read |
| Guarantee | event-driven | event-driven boundary, protocol-written state | probabilistic |

The native hook raises the guarantee for detecting compact boundaries. It does
not prove that the agent maintained complete state, nor that ASCS improves
productivity; both remain measurement targets.

Run `python3 -B scripts/smoke_codex_compact.py` to exercise the exact hook as a
JSON stdin/stdout subprocess for both triggers. This does not start Codex and
does not close the live runtime-dispatch gap; see
[`codex-compact-synthetic-smoke.md`](../codex-compact-synthetic-smoke.md).
