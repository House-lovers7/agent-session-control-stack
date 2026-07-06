#!/usr/bin/env bash
# Read-only stack demo checker.
# Repo-side checks read from $1; environment-side checks read from $HOME.
# Verified against upstream behavior as of 2026-07-05.
# Distinct from scripts/ascs.py's experiment doctor.

set -u

usage() {
  printf 'Usage: stack-doctor.sh <project-root>\n' >&2
}

if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  usage
  exit 2
fi

project_root=$1
violations=0

report_violation() {
  violations=$((violations + 1))
  printf 'violation: %s\n' "$1" >&2
}

settings_file="${HOME}/.claude/settings.json"
if [ -f "$settings_file" ] && grep -Fq 'claude-compact-warn' "$settings_file"; then
  report_violation "settings mention a claude-compact-warn marker path"
fi

if env | grep -Fq 'claude-compact-warn'; then
  report_violation "environment mentions a claude-compact-warn marker path"
fi

if [ "${COMPACT_PLUS_PRIMARY_BACKEND-}" != "" ]; then
  report_violation "paid opt-in active: COMPACT_PLUS_PRIMARY_BACKEND is set"
fi

if [ "${COMPACT_PLUS_FALLBACK_BACKEND-}" != "" ]; then
  report_violation "paid opt-in active: COMPACT_PLUS_FALLBACK_BACKEND is set"
fi

upstream_pxpipe_models="claude-fable-5,gpt-5.6"
if [ "${PXPIPE_MODELS-}" != "" ] && [ "${PXPIPE_MODELS}" != "$upstream_pxpipe_models" ]; then
  report_violation "PXPIPE_MODELS is not the upstream default; possible widened allowlist"
fi

required_files="
.agent-session/handoff.md
.agent-session/state/current-plan.md
.agent-session/state/decision-log.md
.agent-session/state/failed-attempts.md
.agent-session/state/checkpoint.md
.agent-session/state/recovery-notes.md
"

for relative_path in $required_files; do
  if [ ! -f "${project_root}/${relative_path}" ]; then
    report_violation "missing required state file: ${relative_path}"
  fi
done

if [ "$violations" -gt 0 ]; then
  exit 1
fi

exit 0
