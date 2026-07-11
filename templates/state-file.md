<!-- ascs-state-metadata
state_schema_version: 1
repository: <owner/repository>
branch: <branch name>
commit: <40-character commit SHA>
session_id: <opaque session ID>
updated_at: <ISO-8601 UTC>
expires_at: <ISO-8601 UTC, no more than 7 days after updated_at>
-->

# Compact Prep State

<!-- 10-section state snapshot. Same sections, names, and order as a
     compact-plus state file, so snapshots are interchangeable across
     Claude Code and Codex sessions. Overwrite this file at each
     checkpoint; history lives in git or in your transcript backups. -->

## Active Plan
<!-- The currently approved plan, in execution order. Link to the plan file if one exists; don't paste bulky content. -->

## Current Phase
<!-- Which step of the plan you are on, and what "done" means for it. -->

## TaskList Summary
<!-- Open tasks: done / in progress / not started. One line each. -->

## Session Decisions
<!-- Decisions made this session, each with its reason. Include rejected options — they are the part a summary loses first. -->

## Constraints and Blockers
<!-- Hard constraints (user instructions, approvals required, budget/time limits) and current blockers. -->

## Worker Topology
<!-- Subagents/workers in flight or planned: who is doing what, and what they will return. -->

## Skills Invoked
<!-- Skills/commands already applied this session, so a resumer doesn't re-run them blindly. -->

## Editing Files
<!-- Files currently being modified, and their intended end state. Exact paths as text. -->

## Failed Attempts
<!-- Approaches that failed or were abandoned: what was tried, what happened, cause hypothesis. Do not retry these without changing something. -->

## Recovery Notes
<!-- What a resumer must know first: traps, environment quirks, "the summary will tell you X but the truth is Y" warnings. -->
