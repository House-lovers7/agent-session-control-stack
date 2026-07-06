#!/bin/sh
# Adapter placeholder for the checkpoint/recovery layer.
# Architectural truth: compact-plus normally registers its own plugin hooks.
# This file is a manual invocation point, not a replacement for upstream hooks.
# It does not decide or advise compaction timing, inject additionalContext, or
# write the compact-plus warn marker. session-health stays the single compact
# decider in the reference stack.

if [ -z "${COMPACT_PLUS_CHECKPOINT_COMMAND:-}" ]; then
  {
    printf '%s\n' 'compact-plus adapter disabled: COMPACT_PLUS_CHECKPOINT_COMMAND is empty or unset.'
    printf '%s\n' 'Install the upstream checkpoint/recovery tool yourself, then set COMPACT_PLUS_CHECKPOINT_COMMAND to the command of your choice.'
    printf '%s\n' 'Upstream links are listed in ../../../../ATTRIBUTION.md.'
  } >&2
  exit 1
fi

# shellcheck disable=SC2086
exec ${COMPACT_PLUS_CHECKPOINT_COMMAND} "$@"
