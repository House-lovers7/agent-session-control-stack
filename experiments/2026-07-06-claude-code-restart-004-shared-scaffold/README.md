# Experiment 004 Shared Scaffold

This directory freezes the neutral `.agent-session/` scaffold used by the
treated arms. It contains no fictional task, prior knowledge, or task-specific
hint.

## Pre-run doctor note

The preregistration-time doctor check was:

```text
python3 scripts/exp004.py doctor --target-repo /Users/tg/projects/app_development/supabase-rls-guard --sandbox-root /private/tmp/ascs-exp004-doctor
```

Result: all readiness checks passed. The only warning was:

```text
WARN Claude Code project-state check: no exact project state match detected
```

Interpretation: the helper found no exact pre-existing Claude Code project
state for the requested sandbox path. This is not a blocker. Before running
an arm, the operator should run the same doctor command again and treat an
exact project-state match as a contamination risk to resolve before start.
