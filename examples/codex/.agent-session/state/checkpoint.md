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

This 10-section snapshot intentionally matches the compact-plus state-file
shape so Claude Code and Codex handoffs can share the same recovery contract.
Overwrite it at each checkpoint; put history in the decision log.

## Active Plan

<!-- Approved plan in execution order. Link to the plan file if one exists. -->

## Current Phase

<!-- Current phase and what done means for it. -->

## TaskList Summary

<!-- Done / in-progress / not-started tasks. -->

## Session Decisions

<!-- Decisions made this session, including rejected options and reasons. -->

## Constraints and Blockers

<!-- User constraints, approval gates, environment constraints, blockers. -->

## Worker Topology

<!-- Subagents or workers in flight or planned, and what each returns. -->

## Skills Invoked

<!-- Skills, workflows, or special procedures already applied. -->

## Editing Files

<!-- Files being modified and intended end state. Use exact paths. -->

## Failed Attempts

<!-- Failed or abandoned approaches, observed result, and cause hypothesis. -->

## Recovery Notes

<!-- What a resumer must know before acting. -->
