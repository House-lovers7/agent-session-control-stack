#!/bin/sh
# Adapter placeholder for the compression layer.
# Architectural truth: pxpipe is a request-path PROXY, not a hook.
# This file only shows where a proxy start/wrapper command would be wired.
# It compresses nothing itself, does not inject additionalContext, and does not
# write the compact-plus warn marker. session-health stays the single compact
# decider in the reference stack.

if [ -z "${PXPIPE_COMPRESS_COMMAND:-}" ]; then
  {
    printf '%s\n' 'pxpipe adapter disabled: PXPIPE_COMPRESS_COMMAND is empty or unset.'
    printf '%s\n' 'Install the upstream compression proxy yourself, then set PXPIPE_COMPRESS_COMMAND to the command of your choice.'
    printf '%s\n' 'Upstream links: see ATTRIBUTION.md in the agent-session-control-stack repository (https://github.com/House-lovers7/agent-session-control-stack).'
  } >&2
  exit 1
fi

# shellcheck disable=SC2086
exec ${PXPIPE_COMPRESS_COMMAND} "$@"
