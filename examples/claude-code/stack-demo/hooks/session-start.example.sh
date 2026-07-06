#!/usr/bin/env bash
# Disabled placeholder for a possible SessionStart handoff-read reminder.
# A future hook could remind the model to read .agent-session/handoff.md here.
# v0 ships this disabled to preserve the injection budget.
# Experiment 004 is operator-driven: design draft only, no results yet.
exit 0

# shellcheck disable=SC2317
printf '%s\n' 'Read .agent-session/handoff.md before working.'
