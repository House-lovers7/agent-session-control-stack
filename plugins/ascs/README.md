# ascs (plugin)

Read-only doctor for the [Agent Session Control Stack](https://github.com/House-lovers7/agent-session-control-stack).

One command, `/ascs:doctor`, which reports:

- which of the 4 layers (Compression / Health Detection / Checkpoint / Recovery) are active in this environment
- whether the **single-compact-decider** rule holds (no compact-warn marker producer wired in)
- the pxpipe lossy-boundary reminder when the proxy is listening

## What it deliberately does not do

- registers **no** hooks and injects **no** context into your sessions
- writes nothing, starts nothing, calls no API
- does not install or configure the upstream tools — each layer stays an explicit, separate opt-in

## Attribution

This plugin only *diagnoses* the composition. The layers themselves are the work of their authors:

- [pxpipe](https://github.com/teamchong/pxpipe) by teamchong — Compression (request-path proxy; not a plugin, not installable from any marketplace)
- [claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health) by House-lovers7 — Health Detection
- [compact-plus](https://github.com/u-ichi/compact-plus) by u-ichi (Yuichi Uemura) — Checkpoint + Recovery

The `ascs` marketplace lists the upstream plugins **by reference**: installing them pulls the authors' original repositories unmodified. See [ATTRIBUTION.md](../../ATTRIBUTION.md).
