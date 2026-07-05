# Agent Session Control Stack Phase 1

This document defines the Phase 1 minimum viable reference architecture for
Claude Code and Codex. Phase 1 is docs-only: it provides templates, examples,
and operating rules. It does not install hooks, start proxies, generate wrapper
commands, or automate measurement.

## Purpose

Agent Session Control Stack separates long-running agent stability into four
layers:

1. Compression: reduce bulky context.
2. Health Detection: decide when a session is hot.
3. Checkpoint: preserve plan, decisions, failed attempts, and worker topology.
4. Recovery: resume from persisted state, treating summaries as hypotheses.

The stack does not replace pxpipe, claude-code-session-health, or compact-plus.
It documents how to compose them for Claude Code and how to express the same
Checkpoint/Recovery contract as a Codex protocol.

## Phase 1 File Map

```text
agent-session-control-stack/
  docs/
    agent-session-control-stack.md
    measurement-checklist.md
  examples/
    codex/
      AGENTS.md
      .agent-session/
        handoff.md
        state/
          checkpoint.md
          current-plan.md
          decision-log.md
          failed-attempts.md
          recovery-notes.md
    claude-code/
      settings.example.json
  templates/
    state-file.md
    session-handoff.md
    decision-log.md
```

Codex and Claude Code runnable examples live under `examples/`. Reusable base
templates live under `templates/`.

## Claude Code Minimum Configuration

Claude Code uses the runtime surfaces that already exist in the upstream tools:

- Compression: pxpipe local proxy.
- Health Detection: claude-code-session-health `UserPromptSubmit` hook.
- Checkpoint and Recovery: compact-plus `PreCompact`, `PostCompact`, and
  recovery injection.

Phase 1 provides only a settings example in
`examples/claude-code/settings.example.json`. It intentionally keeps
compact-plus LLM state-file generation disabled by setting both backend env
vars to `""`, because the default backend can call `claude -p`, which is a
paid API path.

The compact decision owner is session-health. Do not install a statusline or
other marker producer that writes compact-plus warn markers; without that
producer, compact-plus recovery and checkpoint functions can remain available
without becoming a second compact reminder.

pxpipe remains opt-in and manual. Do not put `ANTHROPIC_BASE_URL` in persistent
settings unless the proxy is intentionally run all the time. Byte-exact work
must not depend on pxpipe image compression.

## Codex Minimum Configuration

Codex does not have Claude Code's compact lifecycle hooks in this design.
Phase 1 therefore implements the shared Checkpoint/Recovery contract as a
protocol:

- `examples/codex/AGENTS.md` declares the session control rules.
- `examples/codex/.agent-session/handoff.md` is the single recovery entry
  point.
- `examples/codex/.agent-session/state/checkpoint.md` uses the
  compact-plus-compatible 10-section snapshot.
- `decision-log.md`, `failed-attempts.md`, `current-plan.md`, and
  `recovery-notes.md` preserve the details that summaries often drop.

This is weaker than hooks because it depends on protocol adherence. Phase 2
will measure whether the protocol is actually followed.

## Scope Boundary

Implemented in Phase 1:

- Reference document.
- Codex `AGENTS.md` protocol template.
- Codex `.agent-session/` state templates.
- Claude Code settings example.
- Measurement checklist.

Not implemented in Phase 1:

- Claude Code hook installation.
- compact-plus backend execution.
- pxpipe proxy startup.
- Codex wrapper or automatic health detection.
- Measurement collection scripts.
- GitHub/Gitea PR creation, push, deploy, publish, or upstream communication.

## Source Documents

- `docs/architecture.md`
- `docs/adapter-interface.md`
- `docs/codex/agents-md-draft.md`
- `docs/claude-code/recommended-stack.md`
- `docs/measurement-plan.md`
- `docs/acceptance-criteria.md`
