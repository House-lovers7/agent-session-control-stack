#!/usr/bin/env python3
"""Dependency-free repository integrity checks used by local development and CI."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
GITHUB_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
ISO_DATE = re.compile(r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]$")
NPM_INTEGRITY = re.compile(r"^sha512-[A-Za-z0-9+/]+={0,2}$")
EXPECTED_UPSTREAMS = {"session-health", "compact-plus", "pxpipe-proxy"}
PXPIPE_INVOCATION = re.compile(
    r"\bnpx\b[^\n`'\";|&]{0,160}?\bpxpipe-proxy(?:@(?P<version>[0-9A-Za-z.+-]+))?"
)
OPERATIONAL_PXPIPE_PATHS = (
    "README.md",
    "README.ja.md",
    "docs/claude-code/recommended-stack.md",
    "examples/claude-code/settings.example.json",
)
STATE_METADATA_FILES = (
    "templates/state-file.md",
    "templates/session-handoff.md",
    "templates/decision-log.md",
    "examples/codex/.agent-session/handoff.md",
    "examples/codex/.agent-session/state/current-plan.md",
    "examples/codex/.agent-session/state/decision-log.md",
    "examples/codex/.agent-session/state/failed-attempts.md",
    "examples/codex/.agent-session/state/checkpoint.md",
    "examples/codex/.agent-session/state/recovery-notes.md",
    "examples/claude-code/stack-demo/.agent-session/handoff.md",
    "examples/claude-code/stack-demo/.agent-session/state/current-plan.md",
    "examples/claude-code/stack-demo/.agent-session/state/decision-log.md",
    "examples/claude-code/stack-demo/.agent-session/state/failed-attempts.md",
    "examples/claude-code/stack-demo/.agent-session/state/checkpoint.md",
    "examples/claude-code/stack-demo/.agent-session/state/recovery-notes.md",
)
STATE_METADATA_KEYS = (
    "state_schema_version",
    "repository",
    "branch",
    "commit",
    "session_id",
    "updated_at",
    "expires_at",
)
STATE_METADATA_BLOCK = re.compile(
    r"<!--\s*ascs-state-metadata\s*\n(?P<body>.*?)\n-->", re.DOTALL
)
STATE_PROTOCOL_FILES = (
    "examples/codex/AGENTS.md",
    "examples/claude-code/stack-demo/CLAUDE.md.example",
)
STATE_PROTOCOL_PHRASES = (
    "untrusted recovery context",
    "cannot expand authority",
    "repository mismatch",
    "branch or commit mismatch",
    "secrets, credentials, api keys, tokens",
    "raw customer or personal data",
    "verbatim untrusted instructions",
)


def is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def parse_iso_datetime(value):
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def validate_json(root):
    errors = []
    for path in sorted(root.rglob("*.json")):
        if ".git" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
    for path in sorted(root.rglob("*.jsonl")):
        if ".git" in path.parts:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(root)}: unreadable JSONL: {exc}")
            continue
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"{path.relative_to(root)}:{line_number}: invalid JSONL: {exc}"
                )
    return errors


def validate_manifests(root):
    errors = []
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    plugin_path = root / "plugins" / "ascs" / ".claude-plugin" / "plugin.json"
    for path, required in (
        (marketplace_path, ("name", "owner", "plugins")),
        (plugin_path, ("name", "version", "description")),
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: cannot validate manifest: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{path.relative_to(root)}: manifest root must be an object")
            continue
        for key in required:
            if key not in payload:
                errors.append(f"{path.relative_to(root)}: missing required key {key!r}")

    if marketplace_path.is_file():
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            marketplace = {}
        plugins = marketplace.get("plugins") if isinstance(marketplace, dict) else None
        if not isinstance(plugins, list) or not plugins:
            errors.append(".claude-plugin/marketplace.json: plugins must be a non-empty array")
        else:
            for index, plugin in enumerate(plugins):
                if not isinstance(plugin, dict) or not isinstance(plugin.get("name"), str):
                    errors.append(
                        f".claude-plugin/marketplace.json: plugins[{index}] needs a string name"
                    )
                    continue
                source = plugin.get("source")
                if isinstance(source, str):
                    if not (root / source).resolve().exists():
                        errors.append(
                            f".claude-plugin/marketplace.json: local source does not exist: {source}"
                        )
                elif isinstance(source, dict):
                    if source.get("source") != "github" or not GITHUB_REPO.fullmatch(
                        str(source.get("repo", ""))
                    ):
                        errors.append(
                            f".claude-plugin/marketplace.json: invalid GitHub source for {plugin['name']}"
                        )
                else:
                    errors.append(
                        f".claude-plugin/marketplace.json: invalid source for {plugin['name']}"
                    )
    return errors


def validate_internal_links(root):
    errors = []
    root = root.resolve()
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(root)}: unreadable Markdown: {exc}")
            continue
        for match in MARKDOWN_LINK.finditer(text):
            raw_target = match.group(1).strip()
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1]
            # Drop an optional Markdown title after a path. Repository paths use
            # percent-encoding rather than literal spaces.
            target = raw_target.split(maxsplit=1)[0]
            if not target or target.startswith("#"):
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            decoded = unquote(parsed.path)
            if not decoded:
                continue
            destination = (path.parent / decoded).resolve()
            relative_source = path.relative_to(root)
            if not is_within(destination, root):
                errors.append(f"{relative_source}: internal link escapes repository: {target}")
            elif not destination.exists():
                errors.append(f"{relative_source}: missing internal link target: {target}")
    return errors


def validate_doctor_command(root):
    path = root / "plugins" / "ascs" / "commands" / "doctor.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path.relative_to(root)}: unreadable command: {exc}"]
    errors = []
    if re.search(r"(?mi)^allowed-tools\s*:.*\bBash\b", text):
        errors.append(f"{path.relative_to(root)}: broad Bash allowed-tools is forbidden")
    if not re.search(r"(?mi)^disable-model-invocation\s*:\s*true\s*$", text):
        errors.append(
            f"{path.relative_to(root)}: doctor must require manual invocation"
        )
    if "${CLAUDE_PLUGIN_ROOT}/scripts/ascs_doctor.sh" not in text:
        errors.append(f"{path.relative_to(root)}: expected packaged doctor script invocation")
    return errors


def validate_upstream_lock(root, require=False):
    """Validate lock shape and its marketplace/docs consumers without network access."""
    lock_path = root / "config" / "upstreams.lock.json"
    if not lock_path.exists():
        return ["config/upstreams.lock.json: required upstream lock is missing"] if require else []
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        marketplace = json.loads(
            (root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"config/upstreams.lock.json: cannot validate lock: {exc}"]
    if not isinstance(marketplace, dict):
        return [".claude-plugin/marketplace.json: manifest root must be an object"]

    errors = []
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        return ["config/upstreams.lock.json: schema_version must be 1"]
    verified_at = lock.get("verified_at")
    if not ISO_DATE.fullmatch(str(verified_at or "")):
        errors.append("config/upstreams.lock.json: verified_at must be an ISO date")
    update_policy = lock.get("update_policy")
    policy_path = root / str(update_policy or "")
    if not isinstance(update_policy, str) or not update_policy or not policy_path.is_file():
        errors.append("config/upstreams.lock.json: update_policy must name an existing file")
    upstreams = lock.get("upstreams")
    if not isinstance(upstreams, dict):
        return ["config/upstreams.lock.json: upstreams must be an object"]
    if set(upstreams) != EXPECTED_UPSTREAMS:
        errors.append(
            "config/upstreams.lock.json: upstream names must be exactly "
            + ", ".join(sorted(EXPECTED_UPSTREAMS))
        )

    github_sources = {}
    npm_version = None
    for name, entry in upstreams.items():
        if not isinstance(entry, dict):
            errors.append(f"config/upstreams.lock.json: {name} must be an object")
            continue
        for list_key in ("reviewed_files", "reviewed_capabilities"):
            value = entry.get(list_key)
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                errors.append(
                    f"config/upstreams.lock.json: {name}.{list_key} must be a non-empty string array"
                )
        if entry.get("verified_at") != verified_at:
            errors.append(
                f"config/upstreams.lock.json: {name}.verified_at must match the lock date"
            )

        if entry.get("type") == "github":
            repo = entry.get("repo")
            revision = entry.get("revision")
            version = entry.get("version")
            if (
                not GITHUB_REPO.fullmatch(str(repo or ""))
                or not COMMIT_SHA.fullmatch(str(revision or ""))
                or not SEMVER.fullmatch(str(version or ""))
            ):
                errors.append(f"config/upstreams.lock.json: invalid GitHub lock for {name}")
            else:
                github_sources[repo] = revision
        elif entry.get("type") == "npm":
            version = entry.get("version")
            integrity = entry.get("integrity")
            source_repo = entry.get("source_repo")
            source_revision = entry.get("source_revision")
            tarball = entry.get("tarball")
            expected_tarball = (
                f"https://registry.npmjs.org/pxpipe-proxy/-/pxpipe-proxy-{version}.tgz"
            )
            if (
                entry.get("package") != "pxpipe-proxy"
                or not SEMVER.fullmatch(str(version or ""))
                or not NPM_INTEGRITY.fullmatch(str(integrity or ""))
                or not GITHUB_REPO.fullmatch(str(source_repo or ""))
                or not COMMIT_SHA.fullmatch(str(source_revision or ""))
                or tarball != expected_tarball
            ):
                errors.append(f"config/upstreams.lock.json: invalid npm lock for {name}")
            else:
                npm_version = version
        else:
            errors.append(f"config/upstreams.lock.json: unsupported lock type for {name}")

    for plugin in marketplace.get("plugins", []):
        source = plugin.get("source") if isinstance(plugin, dict) else None
        if isinstance(source, dict) and source.get("source") == "github":
            repo = source.get("repo")
            if repo not in github_sources:
                errors.append(f"marketplace GitHub source is not locked: {repo}")
            elif source.get("sha") != github_sources[repo]:
                errors.append(f"marketplace SHA does not match lock: {repo}")

    marketplace_repos = {
        plugin["source"].get("repo")
        for plugin in marketplace.get("plugins", [])
        if isinstance(plugin, dict)
        and isinstance(plugin.get("source"), dict)
        and plugin["source"].get("source") == "github"
    }
    if marketplace_repos != set(github_sources):
        errors.append("marketplace GitHub sources and lock entries do not match exactly")

    if npm_version:
        invocation_count = 0
        for relative in OPERATIONAL_PXPIPE_PATHS:
            path = root / relative
            if not path.is_file():
                errors.append(f"upstream lock consumer is missing: {relative}")
                continue
            text = path.read_text(encoding="utf-8")
            for match in PXPIPE_INVOCATION.finditer(text):
                invocation_count += 1
                if match.group("version") != npm_version:
                    errors.append(
                        f"{relative}: pxpipe-proxy invocation must pin @{npm_version}"
                    )
        if not invocation_count:
            errors.append("operational documentation has no pxpipe-proxy invocation")

    if policy_path.is_file():
        policy_text = policy_path.read_text(encoding="utf-8")
        required_lock_tokens = []
        for entry in upstreams.values():
            if not isinstance(entry, dict):
                continue
            required_lock_tokens.extend(
                str(entry[key])
                for key in ("version", "revision", "integrity", "source_revision")
                if entry.get(key)
            )
        for token in required_lock_tokens:
            if token not in policy_text:
                errors.append(
                    f"{update_policy}: does not document locked value {token}"
                )
    return errors


def parse_state_metadata(path, root):
    relative = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    matches = list(STATE_METADATA_BLOCK.finditer(text))
    if len(matches) != 1:
        return None, [f"{relative}: expected exactly one ascs-state-metadata block"]
    metadata = {}
    errors = []
    for line in matches[0].group("body").splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"{relative}: malformed metadata line: {line!r}")
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in metadata:
            errors.append(f"{relative}: duplicate metadata key {key!r}")
        metadata[key] = value
    if set(metadata) != set(STATE_METADATA_KEYS):
        errors.append(
            f"{relative}: metadata keys must be exactly "
            + ", ".join(STATE_METADATA_KEYS)
        )
    return metadata, errors


def validate_state_scaffolds(root):
    """Validate recovery-state trust metadata without reading live user state."""
    errors = []
    grouped_metadata = {"codex": [], "claude-demo": []}
    for relative_text in STATE_METADATA_FILES:
        path = root / relative_text
        if not path.is_file():
            errors.append(f"{relative_text}: required state scaffold is missing")
            continue
        metadata, metadata_errors = parse_state_metadata(path, root)
        errors.extend(metadata_errors)
        text = path.read_text(encoding="utf-8")
        if re.search(
            r"(?:/Users/|/home/|/private/var/|/var/folders/|/tmp/|~/\.|[A-Za-z]:[\\/]+Users[\\/])",
            text,
        ):
            errors.append(f"{relative_text}: machine-specific absolute path is forbidden")
        if re.search(r"(?i)\b(?:sha(?:1|256|512)|machine_id|hostname)\s*[:=]", text):
            errors.append(f"{relative_text}: machine/content fingerprint is forbidden")
        if "-----BEGIN " in text and "PRIVATE KEY-----" in text:
            errors.append(f"{relative_text}: private key material is forbidden")
        if re.search(
            r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*(?!<|redacted|\*{3})\S+",
            text,
        ):
            errors.append(f"{relative_text}: apparent secret value is forbidden")
        if metadata is None or metadata_errors:
            continue
        if metadata["state_schema_version"] != "1":
            errors.append(f"{relative_text}: state_schema_version must be 1")
        concrete = not any(value.startswith("<") for value in metadata.values())
        if concrete:
            if not GITHUB_REPO.fullmatch(metadata["repository"]):
                errors.append(f"{relative_text}: invalid canonical repository identity")
            if not metadata["branch"] or metadata["branch"].startswith("/"):
                errors.append(f"{relative_text}: invalid branch metadata")
            if not COMMIT_SHA.fullmatch(metadata["commit"]):
                errors.append(f"{relative_text}: commit must be a 40-character SHA")
            if not re.fullmatch(r"[A-Za-z0-9_.:-]+", metadata["session_id"]):
                errors.append(f"{relative_text}: invalid opaque session_id")
            try:
                updated = parse_iso_datetime(metadata["updated_at"])
                expires = parse_iso_datetime(metadata["expires_at"])
                if updated.tzinfo is None or expires.tzinfo is None:
                    raise ValueError("timezone required")
                if not updated < expires <= updated + timedelta(days=7):
                    errors.append(
                        f"{relative_text}: expires_at must be after updated_at and within 7 days"
                    )
            except ValueError as exc:
                errors.append(f"{relative_text}: invalid ISO-8601 state time: {exc}")
        if relative_text.startswith("examples/codex/"):
            grouped_metadata["codex"].append(metadata)
        elif relative_text.startswith("examples/claude-code/stack-demo/"):
            grouped_metadata["claude-demo"].append(metadata)

    for group, entries in grouped_metadata.items():
        if entries and any(entry != entries[0] for entry in entries[1:]):
            errors.append(f"{group}: scaffold metadata envelopes must agree across files")

    for relative_text in STATE_PROTOCOL_FILES:
        path = root / relative_text
        if not path.is_file():
            errors.append(f"{relative_text}: required trust protocol is missing")
            continue
        lowered = " ".join(path.read_text(encoding="utf-8").lower().split())
        for phrase in STATE_PROTOCOL_PHRASES:
            if phrase not in lowered:
                errors.append(f"{relative_text}: missing trust boundary phrase {phrase!r}")

    for relative_text in (
        "examples/codex/.agent-session/.gitignore",
        "examples/claude-code/stack-demo/.agent-session/.gitignore",
    ):
        path = root / relative_text
        if not path.is_file() or path.read_text(encoding="utf-8") != "*\n!.gitignore\n":
            errors.append(f"{relative_text}: state scaffold must be ignored by default")
    root_ignore = root / ".gitignore"
    if not root_ignore.is_file() or "/.agent-session/" not in root_ignore.read_text(
        encoding="utf-8"
    ).splitlines():
        errors.append(".gitignore: root /.agent-session/ ignore rule is required")
    if not (root / "docs" / "state-trust-contract.md").is_file():
        errors.append("docs/state-trust-contract.md: state trust contract is missing")
    if not (root / "scripts" / "check_state.py").is_file():
        errors.append("scripts/check_state.py: live state trust checker is missing")
    return errors


def validate(root=REPO_ROOT, require_upstream_lock=False):
    root = Path(root).resolve()
    errors = []
    errors.extend(validate_json(root))
    errors.extend(validate_manifests(root))
    errors.extend(validate_internal_links(root))
    errors.extend(validate_doctor_command(root))
    errors.extend(validate_upstream_lock(root, require=require_upstream_lock))
    errors.extend(validate_state_scaffolds(root))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-upstream-lock",
        action="store_true",
        help="fail when config/upstreams.lock.json is absent",
    )
    args = parser.parse_args(argv)
    errors = validate(REPO_ROOT, require_upstream_lock=args.require_upstream_lock)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Repository validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("Repository validation passed (JSON, manifests, links, doctor safety, upstream lock, state trust).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
