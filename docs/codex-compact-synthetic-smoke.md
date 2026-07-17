# Codex compact-hook synthetic smoke

Run the checked-in reference hook as a real JSON stdin/stdout subprocess,
without starting Codex:

```bash
python3 -B scripts/smoke_codex_compact.py
```

The command creates an isolated temporary Git-shaped repository and exercises
synthetic `manual` and `auto` inputs through the exact script shipped at
`examples/codex/.codex/hooks/ascs_compact.py`. It checks:

- `PreCompact` records the matching safe trigger and existing state-file names;
- `PostCompact` closes the same per-session receipt;
- `SessionStart(source=compact)` injects recovery context exactly once;
- parallel manual/auto receipts remain separate;
- transcript paths, raw session IDs, and raw turn IDs are not persisted.

Expected output:

```text
PASS: Codex compact hook manual/auto JSON subprocess contracts, one-shot recovery, and sensitive-value non-persistence
BOUNDARY: no Codex/model/API execution; runtime dispatch remains unverified
```

## Claim boundary

This is stronger than importing the hook as a Python module because it verifies
the executable stdin/stdout JSON boundary. It does **not** start Codex, consume
model quota, change hook trust, or prove that Codex dispatched the hook during
a real `/compact` or auto-compaction. Real runtime dispatch remains unverified
until a separately approved live smoke records both triggers.

## Specification record

- URL: <https://learn.chatgpt.com/docs/hooks>
- Retrieved: 2026-07-16
- Confirmed: `PreCompact` and `PostCompact` match `manual|auto`;
  `SessionStart` matches `compact`; command hooks receive JSON on stdin and may
  return JSON on stdout.
- Unverified: live manual/auto dispatch across every Codex surface and managed
  policy; transcript-path lifetime and transcript format stability.

No paid runner, runtime write, hook trust change, or external send is authorized
by this smoke. Those remain Human Approval Gate operations.
