#!/usr/bin/env python3
"""Read-only ASCS layer diagnosis with fail-closed, sanitized output."""

import hashlib
import json
import os
import platform
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


PXPIPE_HOST = "127.0.0.1"
PXPIPE_PORT = 47821
PLUGIN_LIST_LIMIT = 2 * 1024 * 1024
SETTINGS_FILE_LIMIT = 1024 * 1024
REVIEWED_SNAPSHOT_LIMIT = 64 * 1024
PLUGIN_TREE_FILE_LIMIT = 2048
PLUGIN_TREE_BYTE_LIMIT = 64 * 1024 * 1024
PLUGIN_NAMES = ("session-health", "compact-plus")
VALID_PLUGIN_STATES = {
    "ENABLED",
    "DISABLED",
    "ABSENT",
    "UNKNOWN",
    "VERSION_MISMATCH",
    "CONTENT_MISMATCH",
}
PLUGIN_VERSION_RE = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"
)
REVIEWED_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1] / "reviewed-upstreams.json"
)
CONTENT_REVIEWED_PLUGINS = frozenset({"compact-plus"})


def is_runtime_in_use_marker(relative):
    """Return whether a relative path is a root-level runtime PID marker."""
    return (
        len(relative.parts) == 2
        and relative.parts[0] == ".in_use"
        and relative.parts[1].isascii()
        and relative.parts[1].isdigit()
    )


def say(message=""):
    print(message)


def reject_duplicate_json_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def hash_plugin_tree(root):
    """Return a deterministic content digest without following links.

    sha256-tree-v1 hashes newline-delimited compact JSON records containing a
    POSIX relative path and that file's SHA-256. Git metadata and root-level
    ``.in_use/<pid>`` runtime marker files are excluded; every other regular
    file is included. Links, special files, oversized trees, and trees that
    change shape while being read fail closed.
    """
    candidate = Path(root)
    if candidate.is_symlink():
        raise ValueError("plugin root link is not trusted")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("plugin root is not a directory")

    entries = []
    total_bytes = 0
    for path in resolved.rglob("*"):
        relative = path.relative_to(resolved)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError("plugin tree contains a link")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("plugin tree contains a special file")
        if is_runtime_in_use_marker(relative):
            continue
        entries.append((relative.as_posix(), path))
        if len(entries) > PLUGIN_TREE_FILE_LIMIT:
            raise ValueError("plugin tree has too many files")

    digest = hashlib.sha256()
    for relative, path in sorted(entries):
        data = path.read_bytes()
        total_bytes += len(data)
        if total_bytes > PLUGIN_TREE_BYTE_LIMIT:
            raise ValueError("plugin tree is too large")
        record = json.dumps(
            [relative, hashlib.sha256(data).hexdigest()],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        digest.update(record.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest(), len(entries)


def read_reviewed_plugins(path=REVIEWED_SNAPSHOT_PATH):
    try:
        if path.stat().st_size > REVIEWED_SNAPSHOT_LIMIT:
            raise ValueError("reviewed upstream snapshot is too large")
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        if not isinstance(payload, dict) or payload.get("schema_version") != 2:
            raise ValueError("reviewed upstream snapshot schema is invalid")
        plugins = payload.get("plugins")
        if not isinstance(plugins, dict) or set(plugins) != set(PLUGIN_NAMES):
            raise ValueError("reviewed plugin names are invalid")
        normalized = {}
        for name in PLUGIN_NAMES:
            entry = plugins[name]
            if not isinstance(entry, dict):
                raise ValueError("reviewed plugin entry must be an object")
            version = entry.get("version")
            revision = entry.get("revision")
            allowed_keys = {"version", "revision", "content_integrity"}
            if not set(entry).issubset(allowed_keys):
                raise ValueError("reviewed plugin entry has unknown fields")
            if not isinstance(version, str) or not PLUGIN_VERSION_RE.fullmatch(version):
                raise ValueError("reviewed plugin version is invalid")
            if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
                raise ValueError("reviewed plugin revision is invalid")
            content = entry.get("content_integrity")
            if name in CONTENT_REVIEWED_PLUGINS and not isinstance(content, dict):
                raise ValueError("reviewed plugin content integrity is missing")
            if content is not None:
                if not isinstance(content, dict) or set(content) != {
                    "algorithm",
                    "digest",
                    "file_count",
                    "verified_at",
                }:
                    raise ValueError("reviewed plugin content integrity is invalid")
                if content.get("algorithm") != "sha256-tree-v1":
                    raise ValueError("reviewed plugin content algorithm is invalid")
                if not re.fullmatch(r"[0-9a-f]{64}", str(content.get("digest", ""))):
                    raise ValueError("reviewed plugin content digest is invalid")
                file_count = content.get("file_count")
                if (
                    isinstance(file_count, bool)
                    or not isinstance(file_count, int)
                    or not 0 < file_count <= PLUGIN_TREE_FILE_LIMIT
                ):
                    raise ValueError("reviewed plugin file count is invalid")
                if not re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
                    str(content.get("verified_at", "")),
                ):
                    raise ValueError("reviewed plugin integrity date is invalid")
            normalized[name] = {
                "version": version,
                "revision": revision,
                "content_integrity": content,
            }
        return normalized
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return None


def unknown_plugin_statuses(reviewed_plugins=None):
    reviewed_plugins = reviewed_plugins or {}
    return tuple(
        {
            "name": name,
            "state": "UNKNOWN",
            "installed_versions": (),
            "reviewed_version": reviewed_plugins.get(name, {}).get("version"),
        }
        for name in PLUGIN_NAMES
    )


def verify_installed_content(name, version, install_paths, expected):
    """Return MATCH, MISMATCH, or UNKNOWN without exposing local paths."""
    if not isinstance(expected, dict):
        return "MATCH"
    if not install_paths:
        return "UNKNOWN"
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    try:
        cache_root = (config_dir / "plugins" / "cache").resolve(strict=True)
    except (OSError, RuntimeError):
        return "UNKNOWN"

    seen = set()
    for raw_path in install_paths:
        if (
            not isinstance(raw_path, str)
            or not raw_path
            or len(raw_path) > 4096
            or any(ord(char) < 32 or ord(char) == 127 for char in raw_path)
        ):
            return "UNKNOWN"
        candidate = Path(raw_path)
        if not candidate.is_absolute() or candidate.is_symlink():
            return "UNKNOWN"
        try:
            resolved = candidate.resolve(strict=True)
            relative = resolved.relative_to(cache_root)
        except (OSError, RuntimeError, ValueError):
            return "UNKNOWN"
        if len(relative.parts) < 3 or relative.parts[-2:] != (name, version):
            return "UNKNOWN"
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            digest, file_count = hash_plugin_tree(resolved)
        except (OSError, RuntimeError, UnicodeError, ValueError):
            return "MISMATCH"
        if (
            digest != expected.get("digest")
            or file_count != expected.get("file_count")
        ):
            return "MISMATCH"
    return "MATCH"


def parse_plugin_statuses(payload, reviewed_plugins):
    if not isinstance(payload, list):
        raise ValueError("plugin listing must be an array")
    if (
        not isinstance(reviewed_plugins, dict)
        or set(reviewed_plugins) != set(PLUGIN_NAMES)
    ):
        raise ValueError("reviewed plugin snapshot is unavailable")
    statuses = []
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
                matches.append(
                    (enabled, item.get("version"), item.get("installPath"))
                )
        reviewed_version = reviewed_plugins[target]["version"]
        if not matches:
            state = "ABSENT"
            installed_versions = ()
        elif all(enabled for enabled, _version, _path in matches):
            versions = [version for _enabled, version, _path in matches]
            if not all(
                isinstance(version, str) and PLUGIN_VERSION_RE.fullmatch(version)
                for version in versions
            ):
                state = "UNKNOWN"
                installed_versions = ()
            else:
                installed_versions = tuple(sorted(set(versions)))
                if installed_versions != (reviewed_version,):
                    state = "VERSION_MISMATCH"
                else:
                    integrity = verify_installed_content(
                        target,
                        reviewed_version,
                        [path for _enabled, _version, path in matches],
                        reviewed_plugins[target].get("content_integrity"),
                    )
                    state = {
                        "MATCH": "ENABLED",
                        "MISMATCH": "CONTENT_MISMATCH",
                        "UNKNOWN": "UNKNOWN",
                    }[integrity]
        elif not any(enabled for enabled, _version, _path in matches):
            state = "DISABLED"
            installed_versions = ()
        else:
            state = "UNKNOWN"
            installed_versions = ()
        statuses.append(
            {
                "name": target,
                "state": state,
                "installed_versions": installed_versions,
                "reviewed_version": reviewed_version,
            }
        )
    return tuple(statuses)


def parse_plugin_states(payload):
    """Compatibility wrapper returning state labels only."""
    reviewed_plugins = read_reviewed_plugins()
    if reviewed_plugins is None:
        return tuple(status["state"] for status in unknown_plugin_statuses())
    return tuple(
        status["state"]
        for status in parse_plugin_statuses(payload, reviewed_plugins)
    )


def read_plugin_inventory():
    """Read effective plugin state without permitting background updates."""
    env = os.environ.copy()
    env["DISABLE_AUTOUPDATER"] = "1"
    result = subprocess.run(
        ["claude", "plugin", "list", "--json"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=5,
        check=False,
        env=env,
    )
    if result.returncode != 0 or len(result.stdout) > PLUGIN_LIST_LIMIT:
        raise ValueError("plugin listing unavailable")
    payload = json.loads(
        result.stdout, object_pairs_hook=reject_duplicate_json_keys
    )
    if not isinstance(payload, list):
        raise ValueError("plugin listing must be an array")
    return payload


def plugin_statuses():
    """Use Claude's supported, effective plugin listing; never guess on error."""
    reviewed_plugins = read_reviewed_plugins()
    if reviewed_plugins is None:
        return unknown_plugin_statuses()
    try:
        payload = read_plugin_inventory()
        return parse_plugin_statuses(payload, reviewed_plugins)
    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return unknown_plugin_statuses(reviewed_plugins)


def plugin_states():
    """Compatibility wrapper for callers that only need state labels."""
    return tuple(status["state"] for status in plugin_statuses())


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
        if is_managed and "allowManagedHooksOnly" in settings:
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


def report_compression():
    port_open = loopback_port_open()
    url_state, url_display = sanitize_base_url(os.environ.get("ANTHROPIC_BASE_URL", ""))
    if port_open:
        say(
            "  1 Compression   TCP PORT OPEN at {}:{}; service identity UNVERIFIED".format(
                PXPIPE_HOST, PXPIPE_PORT
            )
        )
    else:
        say(
            "  1 Compression   no listener at {}:{} (layer inactive — optional, opt-in)".format(
                PXPIPE_HOST, PXPIPE_PORT
            )
        )

    if url_state == "LOCAL":
        say("                  this session's sanitized routing target: {}".format(url_display))
        if port_open:
            say("                  address matches the documented pxpipe endpoint; service identity remains UNVERIFIED")
        else:
            say("                  WARNING: the routing target matches pxpipe, but nothing is listening.")
            say("                  This session cannot reach a model until the reviewed proxy command is started or ANTHROPIC_BASE_URL is unset.")
    elif url_state == "OTHER":
        say("                  this session is not routed to the documented pxpipe endpoint ({})".format(url_display))
    elif url_state == "INVALID":
        say("                  WARNING: ANTHROPIC_BASE_URL has an {}; routing status is UNKNOWN".format(url_display))
    else:
        say("                  ANTHROPIC_BASE_URL is unset — this session is not routed through the proxy")
    if port_open:
        say("                  reminder: pxpipe is lossy; keep byte-exact values off allowlisted models. See docs/claude-code/pxpipe-safety.md")


def plugin_message(status, enabled_detail):
    state = status.get("state", "UNKNOWN")
    name = status.get("name", "plugin")
    if state == "ENABLED":
        return "{} plugin: ENABLED ({})".format(name, enabled_detail)
    if state == "DISABLED":
        return "{} plugin: DISABLED".format(name)
    if state == "ABSENT":
        return "{} plugin: not present".format(name)
    if state == "VERSION_MISMATCH":
        installed = ", ".join(status.get("installed_versions", ()))
        reviewed = status.get("reviewed_version")
        return (
            "{} plugin: VERSION MISMATCH (installed {}; reviewed {}; "
            "stable binding UNVERIFIED)"
        ).format(name, installed, reviewed)
    if state == "CONTENT_MISMATCH":
        reviewed = status.get("reviewed_version")
        return (
            "{} plugin: CONTENT MISMATCH (reviewed {}; "
            "stable binding UNVERIFIED)"
        ).format(name, reviewed)
    return (
        "{} plugin: UNKNOWN (Claude plugin listing, install path, content "
        "verification, or reviewed snapshot unavailable or invalid)"
    ).format(name)


def report_plugins(session_health, compact_plus):
    for status in (session_health, compact_plus):
        if status.get("state") not in VALID_PLUGIN_STATES:
            status["state"] = "UNKNOWN"
    say(
        "  2 Health        "
        + plugin_message(
            session_health, "reviewed version; single compact decider"
        )
    )
    compact_message = plugin_message(
        compact_plus, "reviewed version and content"
    )
    say("  3 Checkpoint    " + compact_message)
    say("  4 Recovery      " + compact_message)
    return any(
        status["state"] in {"VERSION_MISMATCH", "CONTENT_MISMATCH"}
        for status in (session_health, compact_plus)
    )


def report_single_decider(session_health, compact_plus):
    producers, settings_incomplete = configured_producers()
    markers = warn_marker_present()
    conflict = False
    if producers:
        summary = ", ".join(producers)
        if session_health == "ENABLED" and compact_plus == "ENABLED" and not settings_incomplete:
            conflict = True
            say("  CONFLICT: compact-warn producer found in {} while both compact decider layers are enabled.".format(summary))
            say("            Remove the marker producer to restore the single-decider composition (architecture.md §4).")
        elif (
            session_health in {"UNKNOWN", "VERSION_MISMATCH", "CONTENT_MISMATCH"}
            or compact_plus in {"UNKNOWN", "VERSION_MISMATCH", "CONTENT_MISMATCH"}
            or settings_incomplete
        ):
            say("  WARNING: compact-warn producer found in {}, but effective state is incomplete; potential conflict not cleared.".format(summary))
        else:
            say("  WARNING: compact-warn producer found in {}, but the two relevant plugins are not both enabled.".format(summary))
            say("           No current conflict is confirmed; remove unused producers to avoid future activation.")
    elif markers:
        say("  WARNING: stale or unattributed compact-warn marker(s) found; no active producer was confirmed in inspected files.")
        say("           Markers alone do not prove a single-decider conflict.")
    else:
        say("  Single-decider rule: NO CONFIRMED CONFLICT in inspected local and file-managed settings")
    if settings_incomplete:
        say("  WARNING: at least one settings file was unreadable or invalid; producer status is incomplete.")
    say("  Scope note: server/MDM/registry-managed and command-line settings cannot be resolved by this read-only script; use Claude /status to verify active sources.")
    return conflict


def main():
    session_health, compact_plus = plugin_statuses()
    session_health_state = session_health["state"]
    compact_plus_state = compact_plus["state"]
    say("ASCS doctor (read-only) — layer status")
    say()
    report_compression()
    plugin_mismatch = report_plugins(session_health, compact_plus)
    say()
    conflict = report_single_decider(session_health_state, compact_plus_state)
    say()
    say("Layers are independently adoptable; version/content mismatch and confirmed conflict are actionable failures. Absent, disabled, and unknown states remain informational.")
    say("Upstream credits: pxpipe (teamchong), claude-code-session-health (House-lovers7), compact-plus (u-ichi) — see ATTRIBUTION.md.")
    return 1 if conflict or plugin_mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
