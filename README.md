# Agent Session Control Stack

**Status: Phase 0 — design documents only.** Public-facing docs and examples land in Phase 1.

Agent Session Control Stack is a reference architecture for long-running AI coding agents.

It separates the problem into four layers:

1. **Compression** — shrink bulky input context ([pxpipe](https://github.com/teamchong/pxpipe))
2. **Health detection** — detect when a session has gone hot and let the model itself propose `/compact`, a fresh session, or delegation ([claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health))
3. **Checkpointing** — preserve plan, decisions, failed attempts, and worker topology before compaction ([compact-plus](https://github.com/u-ichi/compact-plus))
4. **Recovery** — resume safely: *summary is hypothesis, source is truth* (compact-plus + adapter)

It does **not** replace pxpipe, session-health, or compact-plus. It documents how to compose them safely for Claude Code, and how to adapt the same pattern to Codex using AGENTS.md + a state/handoff protocol.

Agent Session Control Stack は、長時間 AI コーディングエージェントのための参照アーキテクチャです。pxpipe / session-health / compact-plus を置き換えるものではありません。それぞれの責務を分離し、Claude Code では hooks/plugin として、Codex では AGENTS.md / state directory / checkpoint-handoff protocol として再現する方法を示します。

## Design documents (Phase 0)

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 4-layer model, per-layer responsibilities, the single-decider rule for compaction, pxpipe safety boundary |
| [docs/hook-responsibilities.md](docs/hook-responsibilities.md) | Claude Code hook × tool matrix, conflict analysis, env conventions |
| [docs/adapter-interface.md](docs/adapter-interface.md) | Runtime-agnostic layer contracts; Claude Code vs Codex bindings |
| [docs/codex/agents-md-draft.md](docs/codex/agents-md-draft.md) | Codex AGENTS.md proposal, `.agent-session/` layout, checkpoint/handoff protocol |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Phase split, division of labor, target file layout |
| [docs/acceptance-criteria.md](docs/acceptance-criteria.md) | What "the integration works" means, per phase |
| [docs/risk-register.md](docs/risk-register.md) | Risks, **unverified points, and withdrawal criteria** |
| [docs/measurement-plan.md](docs/measurement-plan.md) | Before/after metrics and experiment protocol |

## Honest limits

- Individual measurements exist upstream (pxpipe: ~59–70% end-to-end bill reduction; session-health: median 66% in-session reduction from `/compact`, normalized cacheRead/output 233x→83x — consistency evidence, not causality). **The combined effect of all three is unmeasured.** See the risk register before adopting.
- pxpipe is lossy by design. Byte-exact values (hashes, IDs, secrets) must stay text; see the safety boundary in [docs/architecture.md](docs/architecture.md).

## Roadmap

- **Phase 0** — design documents (this commit)
- **Phase 1** — docs-only reference architecture (public README, recommended stacks, examples, templates)
- **Phase 2** — self-verification on real sessions (before/after measurement)
- **Phase 3** — design review, upstream collaboration drafts
- **Phase 4+** — config generator / doctor script / measurement tool / upstream proposals — only if Phase 2 clears the withdrawal criteria

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md). This repository composes ideas from pxpipe (teamchong), claude-code-session-health (House-lovers7), and compact-plus (u-ichi), with respect and without claiming ownership.

## License

MIT — see [LICENSE](LICENSE).
