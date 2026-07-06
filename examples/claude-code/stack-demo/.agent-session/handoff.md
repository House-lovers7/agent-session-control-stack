<!-- Fictional example for the stack demo - not a real session record. -->
# Session Handoff

## Goal
Deliver a fictional web app feature for "Beacon Board": a small team dashboard that lets operators triage incoming customer notes by status, owner, and last response time.

## Current phase
The local mock data model and triage list layout are drafted. The next session should finish the status filter behavior and verify that the empty state still appears when filters match no notes.

## Next action
Open `src/features/triage/filters.ts` and implement the `needs_reply` filter using the exact status keys recorded in `state/checkpoint.md`.

## Open risks / unverified items
The remembered summary says the status key might be `waiting_customer`, but the on-disk checkpoint records `waiting_on_customer`. Re-read the checkpoint before editing. No deploy, migration, destructive command, or external send is part of the next action.

## State pointers
- Plan: `state/current-plan.md`
- Decisions (including rejected options): `state/decision-log.md`
- Failed attempts (do not repeat): `state/failed-attempts.md`
- Latest checkpoint: `state/checkpoint.md`
- Traps and quirks: `state/recovery-notes.md`

## Trust rule
Everything above is a hypothesis written under time pressure.
The referenced files and the actual code are the truth - verify before acting.
