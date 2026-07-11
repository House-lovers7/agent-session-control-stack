# Implementation Notes: Doctor UX Refresh (0.2.0)

## Plan Reference

- User request 2026-07-12: make `/ascs:doctor` supplementary comments more
  user-friendly; strengthen the UI/UX side.

## Decisions

- Presentation only. Detection logic, fail-closed states, exit codes, and the
  hardened evidence-boundary labels (`TCP PORT OPEN … service identity
  UNVERIFIED`, `NO CONFIRMED CONFLICT`, `UNKNOWN`) are unchanged; the UX layer
  adds context around them instead of softening them.
- New output shape: `overall:` verdict line first, per-layer ASCII status tags
  (`[OK] [--] [??] [!!]`), one `role:` line per layer stating the layer slot's
  design purpose, `action:` lines only when there is something to do (healthy
  runs stay quiet), and a closing `legend:` line.
- `role:` lines describe the stack design's purpose for the slot, not verified
  runtime behavior of the installed plugin — the compact-plus status line keeps
  `(behavior depends on its reviewed version)` for that reason.
- `commands/doctor.md` now prescribes the chat-report shape (verdict-first,
  layer table with emoji-mapped tags, ≤3 bullets) while keeping all prior
  safety rules (no `/compact` proposal, preserve UNKNOWN, conflict-first).
- The lossy-boundary reminder says "credentials", not "secrets": the leak test
  asserts the literal substring `secret` never appears in stdout, and static
  text must not trip that check.

## Deviations

- None from the approved scope (script + command template + tests + docs).

## Follow-ups

- Installed plugin cache is still 0.1.0 (old bash version); users see the new
  output only after a plugin update to 0.2.0.
- `docs/user-guide.md` / `.ja.md` sample blocks were refreshed here; other docs
  do not embed doctor output verbatim (checked via grep).
