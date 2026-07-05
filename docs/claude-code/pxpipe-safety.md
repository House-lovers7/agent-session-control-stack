# pxpipe Safety Boundary

pxpipe converts bulky context (large tool results, folded-away history, static system prompt and tool docs) into PNG images to cut input tokens. Upstream reports roughly 59–70% end-to-end bill reduction at Fable list prices.

It is also, by design, **lossy** — and its failure mode is the dangerous kind:

> In upstream's own tests, a 12-character hex string inside a dense image was read back correctly 13/15 times by Fable 5 and **0/15 times by Opus 4.8**. Misreads are not errors; they are **silent confabulation** — the model confidently states a wrong value. Upstream documents a real incident of a confidently misremembered person's name from imaged history.

## What may be imaged, and what must stay text

```
Image OK:
  - old conversation history
  - long logs
  - bulky prose
  - tool docs
  - repeated explanations

Keep as text:
  - file paths
  - commit SHAs
  - API keys / secrets
  - migration names
  - deploy targets
  - exact IDs
  - hashes
  - commands with destructive effects
```

## The limitation you must know before relying on this list

**You cannot enforce the list above through pxpipe configuration when running it via `npx`.** Per-category toggles (e.g., "compress tool results but not reminders") exist in the library's `TransformOptions`, but the proxy/CLI layer does not expose them. Verified against upstream source on 2026-07-05.

The controls you actually have:

| Control | Mechanism | Use for |
|---|---|---|
| Model allowlist | `PXPIPE_MODELS` (default: `claude-fable-5,gpt-5.6`) | only allowlisted models get imaged requests; models with high misread rates (Opus 4.7/4.8, GPT 5.5) are excluded by default — don't widen this |
| Route byte-exact work away | `CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-4-6`, or `model:` in agent frontmatter | send hash/ID/secret-sensitive work to a subagent on a non-allowlisted model, so it bypasses compression entirely |
| Permanent off | `PXPIPE_MODELS=off` | disable imaging while keeping the proxy in place |
| Temporary passthrough | `PXPIPE_DISABLE=1` | A/B testing and incident response; no restart needed, metrics keep recording |

So the safety rule is operational, not configurational: **don't put byte-exact work on the compressed path** — route it to a non-allowlisted model, or flip `PXPIPE_DISABLE=1` for sessions involving deploys, migrations, or anything destructive.

## Incident rule

One confirmed silent-confabulation incident on a byte-exact value ⇒ set `PXPIPE_DISABLE=1` immediately, record the incident in your experiment log, and remove pxpipe from that workflow. The other layers (health / checkpoint / recovery) are unaffected — the stack degrades by layer, not as a whole.
