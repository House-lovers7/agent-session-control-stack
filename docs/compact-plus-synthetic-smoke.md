# compact-plus Synthetic Recovery Smoke

This is a local, no-model contract check for the reviewed compact-plus plugin.
It narrows the gap between static source review and a real Claude Code compact,
without claiming that Claude Code dispatched either hook.

## Run

Prerequisites: the reviewed compact-plus version is installed and enabled, and
the shell tools used by that reviewed plugin (including `bash` and `jq`) are
available.

```bash
python3 -B scripts/smoke_compact_plus.py
```

Expected result:

```text
PASS: compact-plus 1.0.4 reviewed content; synthetic manual/auto marker and one-shot recovery contracts
BOUNDARY: no Claude/model/API/PreCompact execution; runtime dispatch remains unverified
```

The command exits `0` only after both synthetic `manual` and `auto` paths pass.
Any precondition, registration, integrity, marker, injection, or isolation
failure exits `1` with sanitized output.

## What It Executes

The smoke first uses the same effective plugin inventory and reviewed-content
attestation as Doctor. It refuses to continue unless compact-plus is enabled at
the reviewed version and its full cached tree matches the locked
`sha256-tree-v1` digest.

For each trigger it then executes only these two reviewed files:

1. `hooks/compaction-recovery.sh` with a synthetic `PostCompact` payload.
2. `hooks/userpromptsubmit-compaction-recovery.sh` twice with a synthetic
   `UserPromptSubmit` payload.

It verifies all of the following:

- `hooks.json` covers both `manual` and `auto` PostCompact triggers.
- PostCompact creates the session marker and clears the reminder cooldown.
- the next prompt receives valid `[COMPACTION RECOVERY]` additional context.
- the marker is consumed and a second prompt receives no recovery injection.
- the supplied `compact_summary` sentinel is not copied into recovery context.
- plugin content still matches the reviewed digest after execution.

## Safety Boundary

- Plugin inventory runs with automatic updates disabled.
- Hook execution gets fresh isolated `HOME`, `TMPDIR`, transcript, and work
  directories that are removed after the check.
- API credentials and the caller's other environment variables are not passed
  to the hooks.
- `COMPACT_PLUS_PRIMARY_BACKEND` and
  `COMPACT_PLUS_FALLBACK_BACKEND` are explicitly present and empty.
- PreCompact, transcript backup, state summary generation, Claude, model/API
  calls, user settings, and real session files are not used.

This is stronger than static inspection but weaker than a runtime smoke. It
does **not** prove that the current Claude Code build dispatches PostCompact or
UserPromptSubmit for a real manual `/compact` or auto-compaction. That remaining
test can consume a signed-in Claude allowance and therefore stays behind a
separate Human Approval Gate. The official event schema and matcher contract
are documented in the [Claude Code hooks reference](https://code.claude.com/docs/en/hooks).

CI runs the synthetic harness against local fake hooks to protect its contract;
it cannot claim evidence about a developer's installed compact-plus cache. The
reviewed installed-plugin command above is the local evidence step.
