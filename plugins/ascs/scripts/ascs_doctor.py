#!/usr/bin/env python3
"""Read-only ASCS layer diagnosis with fail-closed, sanitized output."""

import json
import os
import platform
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


PXPIPE_HOST = "127.0.0.1"
PXPIPE_PORT = 47821
PLUGIN_LIST_LIMIT = 2 * 1024 * 1024
SETTINGS_FILE_LIMIT = 1024 * 1024
PLUGIN_NAMES = ("session-health", "compact-plus")
VALID_PLUGIN_STATES = {"ENABLED", "DISABLED", "ABSENT", "UNKNOWN"}


def say(message=""):
    print(message)


def parse_plugin_states(payload):
    if not isinstance(payload, list):
        raise ValueError("plugin listing must be an array")
    states = []
    for target in PLUGIN_NAMES:
        matches = []
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("plugin entry must be an object")
            plugin_id = item.get("id")
            if isinstance(plugin_id, str) and plugin_id.split("@", 1)[0] == target:
                enabled = item.get("enabled")
                if not isinstance(enabled, bool):
                    raise ValueError("enabled must be boolean")
                matches.append(enabled)
        if not matches:
            states.append("ABSENT")
        elif all(matches):
            states.append("ENABLED")
        elif not any(matches):
            states.append("DISABLED")
        else:
            states.append("UNKNOWN")
    return tuple(states)


def plugin_states():
    """Use Claude's supported, effective plugin listing; never guess on error."""
    try:
        result = subprocess.run(
            ["claude", "plugin", "list", "--json"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > PLUGIN_LIST_LIMIT:
            raise ValueError("plugin listing unavailable")
        return parse_plugin_states(json.loads(result.stdout))
    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return ("UNKNOWN", "UNKNOWN")


def sanitize_base_url(raw, expected_port=PXPIPE_PORT):
    if not raw:
        return ("UNSET", "<unset>")
    if len(raw) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return ("INVALID", "<invalid or unsafe value redacted>")
    try:
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("unsupported URL")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except (TypeError, ValueError):
        return ("INVALID", "<invalid or unsafe value redacted>")

    host = parsed.hostname.lower().rstrip(".")
    if host in {"127.0.0.1", "localhost", "::1"} and port == expected_port:
        host_display = "[::1]" if host == "::1" else host
        display = "{}://{}:{}".format(parsed.scheme, host_display, port)
        if (
            parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            display += " (credentials/path/query redacted)"
        return ("LOCAL", display)
    return ("OTHER", "<non-pxpipe address redacted>")


def loopback_port_open(host=PXPIPE_HOST, port=PXPIPE_PORT):
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def contains_marker(value):
    if isinstance(value, str):
        return "claude-compact-warn" in value
    if isinstance(value, dict):
        return any(contains_marker(key) or contains_marker(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_marker(item) for item in value)
    return False


def deep_merge(lower, higher):
    """Apply Claude's object merge rule while letting higher scalars win."""
    if not isinstance(lower, dict) or not isinstance(higher, dict):
        return higher
    merged = dict(lower)
    for key, value in higher.items():
        merged[key] = deep_merge(merged[key], value) if key in merged else value
    return merged


def settings_sources():
    """Return known file scopes in low-to-high precedence order."""
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    sources = [
        (config_dir / "settings.json", "user settings"),
        (project_dir / ".claude" / "settings.json", "project settings"),
        (project_dir / ".claude" / "settings.local.json", "project-local settings"),
    ]
    if platform.system() == "Darwin":
        managed_root = Path("/Library/Application Support/ClaudeCode")
    else:
        managed_root = Path("/etc/claude-code")
    sources.append((managed_root / "managed-settings.json", "file-managed settings"))
    managed_dir = managed_root / "managed-settings.d"
    try:
        sources.extend(
            (path, "file-managed settings directory")
            for path in sorted(managed_dir.glob("*.json"))
        )
    except OSError:
        pass
    return sources


def read_settings(path):
    try:
        if path.stat().st_size > SETTINGS_FILE_LIMIT:
            raise ValueError("settings file too large")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("settings root must be an object")
        return payload
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return False


def configured_producers():
    """Resolve known statusLine precedence and additive hook producers."""
    effective_statusline = None
    effective_statusline_label = None
    effective_disable_all_hooks = False
    effective_managed_hooks_only = False
    hook_labels = []
    incomplete = False
    for path, label in settings_sources():
        settings = read_settings(path)
        if settings is None:
            continue
        if settings is False:
            incomplete = True
            continue
        is_managed = label.startswith("file-managed")
        if "statusLine" in settings:
            effective_statusline = deep_merge(effective_statusline, settings["statusLine"])
            if contains_marker(effective_statusline):
                if contains_marker(settings["statusLine"]):
                    effective_statusline_label = label
            else:
                effective_statusline_label = None
        if contains_marker(settings.get("hooks")):
            hook_labels.append((label, is_managed))
        if "disableAllHooks" in settings:
            if isinstance(settings["disableAllHooks"], bool):
                effective_disable_all_hooks = settings["disableAllHooks"]
            else:
                incomplete = True
        if "allowManagedHooksOnly" in settings:
            if isinstance(settings["allowManagedHooksOnly"], bool):
                effective_managed_hooks_only = settings["allowManagedHooksOnly"]
            else:
                incomplete = True

    if effective_disable_all_hooks:
        return [], incomplete

    labels = [
        label
        for label, is_managed in hook_labels
        if not effective_managed_hooks_only or is_managed
    ]
    if contains_marker(effective_statusline) and effective_statusline_label:
        labels.append(effective_statusline_label)
    # Preserve order while removing duplicate, fixed labels.
    labels = list(dict.fromkeys(labels))
    return labels, incomplete


def warn_marker_present():
    warn_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "claude-compact-warn"
    try:
        if not warn_dir.is_dir():
            return False
        for _root, _dirs, files in os.walk(str(warn_dir), followlinks=False):
            if files:
                return True
    except OSError:
        return False
    return False


# Presentation tags. Detection stays fail-closed; tags only summarize it.
TAG_ACTIVE = "[OK]"
TAG_INACTIVE = "[--]"
TAG_UNVERIFIED = "[??]"
TAG_ACTION = "[!!]"


def compression_tag(port_open, url_state):
    if url_state == "INVALID" or (url_state == "LOCAL" and not port_open):
        return TAG_ACTION
    return TAG_UNVERIFIED if port_open else TAG_INACTIVE


def report_compression(port_open, url_state, url_display):
    say("{} 1 Compression — pxpipe proxy (optional, opt-in)".format(
        compression_tag(port_open, url_state)))
    say("     role: compress older history to save tokens before it reaches the model")
    if port_open:
        say("     status: TCP PORT OPEN at {}:{}; service identity UNVERIFIED".format(
            PXPIPE_HOST, PXPIPE_PORT))
    else:
        say("     status: no listener at {}:{} — layer not in use, which is fine".format(
            PXPIPE_HOST, PXPIPE_PORT))

    if url_state == "LOCAL":
        say("     this session: sanitized routing target is {}".format(url_display))
        if port_open:
            say("     note: the address matches the documented pxpipe endpoint; service identity remains UNVERIFIED")
        else:
            say("     WARNING: the routing target matches pxpipe, but nothing is listening.")
            say("     action: start the reviewed proxy command or unset ANTHROPIC_BASE_URL;")
            say("             until then this session cannot reach a model.")
    elif url_state == "OTHER":
        say("     this session: not routed to the documented pxpipe endpoint ({})".format(url_display))
    elif url_state == "INVALID":
        say("     WARNING: ANTHROPIC_BASE_URL has an {}; routing status is UNKNOWN".format(url_display))
        say("     action: inspect ANTHROPIC_BASE_URL in this shell, then correct or unset it.")
    else:
        say("     this session: ANTHROPIC_BASE_URL is unset — not routed through the proxy")
    if port_open:
        say("     note: pxpipe is lossy by design; keep byte-exact values (hashes, commit SHAs,")
        say("           IDs, credentials, exact paths) off allowlisted models routed through it.")
        say("           See docs/claude-code/pxpipe-safety.md")


def report_plugins(session_health, compact_plus):
    plugin_tags = {
        "ENABLED": TAG_ACTIVE,
        "DISABLED": TAG_INACTIVE,
        "ABSENT": TAG_INACTIVE,
        "UNKNOWN": TAG_UNVERIFIED,
    }
    health_messages = {
        "ENABLED": "session-health plugin: ENABLED (single compact decider)",
        "DISABLED": "session-health plugin: DISABLED",
        "ABSENT": "session-health plugin: not present",
        "UNKNOWN": "session-health plugin: UNKNOWN (Claude plugin listing unavailable or invalid)",
    }
    compact_messages = {
        "ENABLED": "compact-plus plugin: ENABLED (behavior depends on its reviewed version)",
        "DISABLED": "compact-plus plugin: DISABLED",
        "ABSENT": "compact-plus plugin: not present",
        "UNKNOWN": "compact-plus plugin: UNKNOWN (Claude plugin listing unavailable or invalid)",
    }
    session_health = session_health if session_health in VALID_PLUGIN_STATES else "UNKNOWN"
    compact_plus = compact_plus if compact_plus in VALID_PLUGIN_STATES else "UNKNOWN"
    say("{} 2 Health — {}".format(plugin_tags[session_health], health_messages[session_health]))
    say("     role: watch session growth; the single layer that advises compaction")
    if session_health == "UNKNOWN" or compact_plus == "UNKNOWN":
        say("     check: run `claude plugin list` to see the authoritative plugin state")
    say()
    say("{} 3 Checkpoint — {}".format(plugin_tags[compact_plus], compact_messages[compact_plus]))
    say("     role: back up the transcript and captured state right before compaction")
    say()
    say("{} 4 Recovery — {}".format(plugin_tags[compact_plus], compact_messages[compact_plus]))
    say("     role: offer the saved state back to the session right after compaction")


def classify_single_decider(session_health, compact_plus):
    """Return (kind, producers, settings_incomplete) without printing."""
    producers, settings_incomplete = configured_producers()
    if producers:
        if session_health == "ENABLED" and compact_plus == "ENABLED" and not settings_incomplete:
            kind = "conflict"
        elif session_health == "UNKNOWN" or compact_plus == "UNKNOWN" or settings_incomplete:
            kind = "producer-unclear"
        else:
            kind = "producer-inactive"
    elif warn_marker_present():
        kind = "stale-markers"
    else:
        kind = "clear"
    return kind, producers, settings_incomplete


def report_single_decider(kind, producers, settings_incomplete):
    say("Single-decider check — exactly one layer may advise compaction")
    summary = ", ".join(producers)
    if kind == "conflict":
        say("  CONFLICT: compact-warn producer found in {} while both compact decider layers are enabled.".format(summary))
        say("            Remove the marker producer to restore the single-decider composition (architecture.md §4).")
    elif kind == "producer-unclear":
        say("  WARNING: compact-warn producer found in {}, but effective state is incomplete; potential conflict not cleared.".format(summary))
    elif kind == "producer-inactive":
        say("  WARNING: compact-warn producer found in {}, but the two relevant plugins are not both enabled.".format(summary))
        say("           No current conflict is confirmed; remove unused producers to avoid future activation.")
    elif kind == "stale-markers":
        say("  WARNING: stale or unattributed compact-warn marker(s) found; no active producer was confirmed in inspected files.")
        say("           Markers alone do not prove a single-decider conflict.")
    else:
        say("  NO CONFIRMED CONFLICT in inspected local and file-managed settings")
    if settings_incomplete:
        say("  WARNING: at least one settings file was unreadable or invalid; producer status is incomplete.")
    say("  scope: server/MDM/registry-managed and command-line settings cannot be resolved by this")
    say("         read-only script; use Claude /status to verify active sources.")


def overall_line(kind, settings_incomplete, port_open, url_state):
    if kind == "conflict":
        return "overall: action required — two layers are set up to advise compaction (see Single-decider check)"
    warnings = 0
    if kind in {"producer-unclear", "producer-inactive", "stale-markers"}:
        warnings += 1
    if settings_incomplete:
        warnings += 1
    if url_state == "INVALID" or (url_state == "LOCAL" and not port_open):
        warnings += 1
    if warnings:
        return "overall: no confirmed conflict, but {} warning(s) below are worth a look".format(warnings)
    return "overall: all clear — nothing needs your attention right now"


def main():
    session_health, compact_plus = plugin_states()
    port_open = loopback_port_open()
    url_state, url_display = sanitize_base_url(os.environ.get("ANTHROPIC_BASE_URL", ""))
    kind, producers, settings_incomplete = classify_single_decider(session_health, compact_plus)

    say("ASCS doctor (read-only) — layer status")
    say(overall_line(kind, settings_incomplete, port_open, url_state))
    say()
    report_compression(port_open, url_state, url_display)
    say()
    report_plugins(session_health, compact_plus)
    say()
    report_single_decider(kind, producers, settings_incomplete)
    say()
    say("legend: [OK] active   [--] not in use (fine)   [??] cannot be verified from here   [!!] needs attention")
    say("Layers are independently adoptable; absent, disabled, and unknown states are informational unless a confirmed conflict is shown.")
    say("Upstream credits: pxpipe (teamchong), claude-code-session-health (House-lovers7), compact-plus (u-ichi) — see ATTRIBUTION.md.")
    return 1 if kind == "conflict" else 0


if __name__ == "__main__":
    raise SystemExit(main())
