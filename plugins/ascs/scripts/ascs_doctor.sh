#!/usr/bin/env bash
# ascs doctor — read-only diagnosis of the Agent Session Control Stack layers.
#
# Reports which layers are active in THIS environment and checks the
# single-compact-decider rule from docs/architecture.md §4.
# Writes nothing, starts nothing, calls no API, changes no config.
#
# Exit codes: 0 = no conflict detected, 1 = single-decider conflict detected.
# Missing layers are informational (the stack is adoptable layer by layer),
# never an error.
set -uo pipefail

conflict=0

say() { printf '%s\n' "$*"; }

INSTALLED="${HOME}/.claude/plugins/installed_plugins.json"

has_plugin() {
  [[ -f "$INSTALLED" ]] || return 1
  python3 - "$1" "$INSTALLED" <<'PY' 2>/dev/null
import json, sys
name, path = sys.argv[1], sys.argv[2]
d = json.load(open(path))
sys.exit(0 if any(k.split("@")[0] == name for k in d.get("plugins", {})) else 1)
PY
}

say "ASCS doctor (read-only) — layer status"
say ""

# --- Layer 1: Compression (pxpipe, request-path proxy — not a plugin) ------
if (exec 3<>/dev/tcp/127.0.0.1/47821) 2>/dev/null; then
  exec 3>&- 2>/dev/null || true
  say "  1 Compression   pxpipe proxy: LISTENING on 127.0.0.1:47821"
  if [[ -n "${ANTHROPIC_BASE_URL:-}" ]]; then
    say "                  this session's ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL}"
  else
    say "                  note: this session's ANTHROPIC_BASE_URL is unset — this session is NOT routed through the proxy"
  fi
  say "                  reminder: pxpipe is lossy by design; keep byte-exact work (hashes, IDs, secrets) off allowlisted models. See docs/claude-code/pxpipe-safety.md"
else
  say "  1 Compression   pxpipe proxy: not listening on 127.0.0.1:47821 (layer inactive — optional, opt-in)"
fi

# --- Layer 2: Health Detection (session-health plugin) ----------------------
if has_plugin session-health; then
  say "  2 Health        session-health plugin: INSTALLED (single compact decider)"
else
  say "  2 Health        session-health plugin: not installed (no hot-session detection, no compact decider)"
fi

# --- Layers 3+4: Checkpoint + Recovery (compact-plus plugin) ----------------
if has_plugin compact-plus; then
  say "  3 Checkpoint    compact-plus plugin: INSTALLED (transcript backup + state capture on PreCompact)"
  say "  4 Recovery      compact-plus plugin: INSTALLED (recovery injection after compaction)"
else
  say "  3 Checkpoint    compact-plus plugin: not installed"
  say "  4 Recovery      compact-plus plugin: not installed"
fi

say ""

# --- Single-decider rule (architecture.md §4) --------------------------------
# The compact-plus reminder only fires when an external statusline writes a
# warn marker. If a producer is wired in, two components advise compaction.
WARN_DIR="${TMPDIR:-/tmp}/claude-compact-warn"
warn_markers=0
[[ -d "$WARN_DIR" ]] && warn_markers=$(find "$WARN_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')

producer=""
SETTINGS="${HOME}/.claude/settings.json"
if [[ -f "$SETTINGS" ]] && grep -q "claude-compact-warn" "$SETTINGS" 2>/dev/null; then
  producer="statusline/hook in ~/.claude/settings.json references claude-compact-warn"
fi

if [[ -n "$producer" || "$warn_markers" -gt 0 ]]; then
  conflict=1
  say "  CONFLICT: a compact-warn marker producer is active (${producer:-markers present in $WARN_DIR})."
  say "            Two components now advise compaction. The stack designates session-health as the single decider;"
  say "            remove the marker producer to restore the composition (architecture.md §4)."
else
  say "  Single-decider rule: OK (no compact-warn marker producer detected; compact-plus reminder stays off by construction)"
fi

say ""
say "Layers are independently adoptable; 'not installed' is informational, not an error."
say "Upstream credits: pxpipe (teamchong), claude-code-session-health (House-lovers7), compact-plus (u-ichi) — see ATTRIBUTION.md."

exit "$conflict"
