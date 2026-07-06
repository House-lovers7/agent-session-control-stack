#!/bin/sh
# Adapter placeholder for the health detection layer.
# Architectural truth: session-health normally registers its own plugin hooks.
# This file is a manual invocation point, not a replacement for upstream hooks.
# It does not decide or advise compaction timing, inject additionalContext, or
# write the compact-plus warn marker. session-health stays the single compact
# decider in the reference stack.

if [ -z "${SESSION_HEALTH_CHECK_COMMAND:-}" ]; then
  {
    printf '%s\n' 'session-health adapter disabled: SESSION_HEALTH_CHECK_COMMAND is empty or unset.'
    printf '%s\n' 'Install the upstream health detection tool yourself, then set SESSION_HEALTH_CHECK_COMMAND to the command of your choice.'
    printf '%s\n' 'Upstream links are listed in ../../../../ATTRIBUTION.md.'
  } >&2
  exit 1
fi

# shellcheck disable=SC2086
exec ${SESSION_HEALTH_CHECK_COMMAND} "$@"
