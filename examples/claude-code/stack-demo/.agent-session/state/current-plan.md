<!-- Fictional example for the stack demo - not a real session record. -->
<!-- ascs-state-metadata
state_schema_version: 1
repository: example/beacon-board
branch: feature/triage-filter
commit: 1111111111111111111111111111111111111111
session_id: demo-session-002
updated_at: 2026-07-10T00:00:00+00:00
expires_at: 2026-07-17T00:00:00+00:00
-->
# Current Plan

## Goal
Build the fictional Beacon Board triage view for a demo-only web app.

## Plan
1. Define the note status keys and owner filter behavior.
2. Build a compact triage list with status, owner, and last response age.
3. Add a `needs_reply` filter that selects notes with status `waiting_on_customer` or `unassigned`.
4. Verify the empty state for filters with no matches.
5. Update handoff and recovery notes before stopping.

## Current step
Step 3 is next. Treat `waiting_on_customer` in `state/checkpoint.md` as a candidate and verify it against current typed source first.

## Done means
The fictional filter behavior is described consistently across the state files, and the next reader can resume without relying on remembered summaries.
