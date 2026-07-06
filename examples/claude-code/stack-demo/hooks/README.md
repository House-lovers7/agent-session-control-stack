# Hooks and Adapter Demo

This stack adds no injecting hooks and no second compact decider. session-health remains the single compact decider; the demo does not write the compact-plus warn marker.

Scripts in this directory are read-only checks, disabled placeholders, or manual adapter placeholders. They do not inject `additionalContext` or register as hooks.

- `stack-doctor.sh`: read-only local checker for the demo state files and selected environment-side settings.
- `session-start.example.sh`: disabled placeholder showing where a SessionStart handoff-read reminder would go in a future experiment or operator-owned setup.
- `session-health-check.sh`: adapter placeholder for the health detection layer.
- `compact-plus-checkpoint.sh`: adapter placeholder for the checkpoint/recovery layer.
- `pxpipe-compress.sh`: adapter placeholder for the compression proxy layer.

## Adapter contract

The three adapter placeholders do not implement, vendor, or hardcode upstream CLIs. The user installs upstream tools independently, then sets an env var to the command of their choice. If the env var is empty or unset, the adapter exits 1 with an explanation.

| Script | Env var | Empty behavior |
|---|---|---|
| `session-health-check.sh` | `SESSION_HEALTH_CHECK_COMMAND` | Disabled; prints health detection setup explanation to stderr. |
| `compact-plus-checkpoint.sh` | `COMPACT_PLUS_CHECKPOINT_COMMAND` | Disabled; prints checkpoint/recovery setup explanation to stderr. |
| `pxpipe-compress.sh` | `PXPIPE_COMPRESS_COMMAND` | Disabled; prints compression proxy setup explanation to stderr. |

When an env var is set, the adapter `exec`s that command and passes `"$@"` through.

None of the five scripts writes a `claude-compact-warn` marker.
