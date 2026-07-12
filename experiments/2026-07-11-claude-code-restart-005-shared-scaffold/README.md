# Experiment 005 Shared Scaffold

This directory freezes the neutral `.agent-session/` scaffold used by the
treated arms of Experiment 005. It contains no fictional task, prior
knowledge, or task-specific hint. The content is the Experiment 004 shared
scaffold copied unchanged (except the experiment number in the neutral
header comment), per the 005 design's inheritance-by-reference rule.

## Pre-run doctor note

To be filled at pre-registration time: run

```text
python3 scripts/exp005.py doctor --target-repo <supabase-rls-guard path> --sandbox-root <sandbox root>
```

and record the result here before any arm starts. Treat an exact Claude
Code project-state match as a contamination risk to resolve before start
(the 004 precedent).
