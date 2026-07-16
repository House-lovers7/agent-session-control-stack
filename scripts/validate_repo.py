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
TREE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_UPSTREAMS = {"session-health", "compact-plus", "pxpipe-proxy"}
REVIEWED_PLUGIN_UPSTREAMS = {"session-health", "compact-plus"}
CONTENT_PINNED_UPSTREAMS = {"compact-plus"}
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
IMPLEMENTATION_STATUS_MARKERS = (
    "Current implementation status (2026-07-13)",
    "Phase 2 measurement harness: implemented",
    "Install-state Doctor: implemented early as a safety diagnostic",
    "Synthetic compact-plus recovery smoke: implemented",
    "Automated benefit measurement: not implemented",
    "Full-stack composition benefit: unvalidated",
)
IMPLEMENTED_STATUS_FILES = {
    "Phase 2 measurement harness: implemented": "scripts/ascs.py",
    "Install-state Doctor: implemented early as a safety diagnostic": (
        "plugins/ascs/scripts/ascs_doctor.py"
    ),
    "Synthetic compact-plus recovery smoke: implemented": (
        "scripts/smoke_compact_plus.py"
    ),
}
IMPROVEMENT_ID = re.compile(r"^IMP-[0-9]{3}$")
IMPROVEMENT_SEVERITIES = {"P0", "P1", "P2", "P3"}
IMPROVEMENT_STATUSES = {
    "open",
    "in_progress",
    "in_verification",
    "verified",
    "deferred",
    "rejected",
}
IMPROVEMENT_DOC_MARKERS = (
    "Reproduce before modify",
    "Human Approval Gate",
    "Close only with evidence",
    "config/improvements.json",
)
COMPACT_SMOKE_ASSETS = (
    "scripts/smoke_compact_plus.py",
    "tests/test_compact_plus_smoke.py",
    "docs/compact-plus-synthetic-smoke.md",
)
COMPACT_SMOKE_SCRIPT_MARKERS = (
    "SUMMARY_SENTINEL",
    "doctor.read_plugin_inventory()",
    '"COMPACT_PLUS_PRIMARY_BACKEND": ""',
    '"COMPACT_PLUS_FALLBACK_BACKEND": ""',
    "run_plugin_smoke",
)
COMPACT_SMOKE_DOC_MARKERS = (
    "manual",
    "auto",
    "no Claude/model/API/PreCompact execution",
    "runtime dispatch remains unverified",
    "Human Approval Gate",
)
CODEX_COMPACT_HOOK_ASSETS = (
    "examples/codex/.codex/hooks.json",
    "examples/codex/.codex/hooks/ascs_compact.py",
    "docs/codex/adapter-design.md",
    "tests/test_codex_compact_hook.py",
)
CODEX_COMPACT_EVENTS = {
    "PreCompact": "^(manual|auto)$",
    "PostCompact": "^(manual|auto)$",
    "SessionStart": "^compact$",
}


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


def validate_implementation_status(root):
    """Keep the historical phase plan aligned with the current repository."""
    path = root / "docs" / "implementation-plan.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"docs/implementation-plan.md: cannot validate current status: {exc}"]

    errors = []
    for marker in IMPLEMENTATION_STATUS_MARKERS:
        if marker not in text:
            errors.append(
                f"docs/implementation-plan.md: missing current status marker {marker!r}"
            )
    for marker, relative in IMPLEMENTED_STATUS_FILES.items():
        if marker in text and not (root / relative).is_file():
            errors.append(
                f"docs/implementation-plan.md: {marker!r} requires existing {relative}"
            )
    return errors


def validate_improvement_loop(root):
    """Validate the audit-to-fix register and its reusable workflow assets."""
    register_path = root / "config" / "improvements.json"
    workflow_path = root / "docs" / "improvement-loop.md"
    template_path = root / "templates" / "improvement-entry.md"
    errors = []
    try:
        register = json.loads(register_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"config/improvements.json: cannot validate register: {exc}"]

    for path, label in (
        (workflow_path, "docs/improvement-loop.md"),
        (template_path, "templates/improvement-entry.md"),
    ):
        if not path.is_file():
            errors.append(f"{label}: required improvement-loop asset is missing")
    if workflow_path.is_file():
        workflow_text = workflow_path.read_text(encoding="utf-8")
        for marker in IMPROVEMENT_DOC_MARKERS:
            if marker not in workflow_text:
                errors.append(f"docs/improvement-loop.md: missing marker {marker!r}")

    if not isinstance(register, dict) or register.get("schema_version") != 1:
        return errors + ["config/improvements.json: schema_version must be 1"]
    if register.get("workflow") != "docs/improvement-loop.md":
        errors.append("config/improvements.json: workflow must name docs/improvement-loop.md")
    if register.get("template") != "templates/improvement-entry.md":
        errors.append(
            "config/improvements.json: template must name templates/improvement-entry.md"
        )
    items = register.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["config/improvements.json: items must be a non-empty array"]

    required = {
        "id",
        "title",
        "severity",
        "status",
        "verified_at",
        "verification_result",
        "evidence",
        "assets",
        "verification",
        "next_gate",
    }
    seen = set()
    for index, item in enumerate(items):
        context = f"config/improvements.json: items[{index}]"
        if not isinstance(item, dict) or set(item) != required:
            errors.append(f"{context} keys must be exactly {', '.join(sorted(required))}")
            continue
        item_id = item["id"]
        if not isinstance(item_id, str) or not IMPROVEMENT_ID.fullmatch(item_id):
            errors.append(f"{context}.id must match IMP-###")
        elif item_id in seen:
            errors.append(f"{context}.id is duplicated: {item_id}")
        else:
            seen.add(item_id)
        if item["severity"] not in IMPROVEMENT_SEVERITIES:
            errors.append(f"{context}.severity is invalid")
        if item["status"] not in IMPROVEMENT_STATUSES:
            errors.append(f"{context}.status is invalid")
        for key in ("title", "evidence", "verification", "next_gate"):
            if not isinstance(item[key], str) or not item[key].strip():
                errors.append(f"{context}.{key} must be a non-empty string")
        if item["status"] == "verified":
            if not isinstance(item["verified_at"], str) or not ISO_DATE.fullmatch(
                item["verified_at"]
            ):
                errors.append(f"{context}.verified_at must be an ISO date")
            if (
                not isinstance(item["verification_result"], str)
                or not item["verification_result"].strip()
            ):
                errors.append(
                    f"{context}.verification_result is required for verified items"
                )
        elif item["verified_at"] is not None or item["verification_result"] not in (
            None,
            "",
        ):
            errors.append(
                f"{context} may set verified_at/result only when status is verified"
            )
        assets = item["assets"]
        if not isinstance(assets, list) or not assets:
            errors.append(f"{context}.assets must be a non-empty array")
            continue
        for asset in assets:
            if not isinstance(asset, str) or not asset:
                errors.append(f"{context}.assets contains an invalid path")
                continue
            candidate = (root / asset).resolve()
            if not is_within(candidate, root) or not candidate.is_file():
                errors.append(f"{context}.assets path does not exist safely: {asset}")
    return errors


def validate_compact_plus_smoke_assets(root):
    """Keep the no-model synthetic smoke executable, tested, and bounded."""
    errors = []
    for relative in COMPACT_SMOKE_ASSETS:
        if not (root / relative).is_file():
            errors.append(f"{relative}: required compact-plus smoke asset is missing")

    script_path = root / "scripts" / "smoke_compact_plus.py"
    if script_path.is_file():
        try:
            script_text = script_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"scripts/smoke_compact_plus.py: cannot read: {exc}")
        else:
            for marker in COMPACT_SMOKE_SCRIPT_MARKERS:
                if marker not in script_text:
                    errors.append(
                        "scripts/smoke_compact_plus.py: missing safety marker "
                        f"{marker!r}"
                    )

    docs_path = root / "docs" / "compact-plus-synthetic-smoke.md"
    if docs_path.is_file():
        try:
            docs_text = docs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"docs/compact-plus-synthetic-smoke.md: cannot read: {exc}"
            )
        else:
            for marker in COMPACT_SMOKE_DOC_MARKERS:
                if marker not in docs_text:
                    errors.append(
                        "docs/compact-plus-synthetic-smoke.md: missing boundary "
                        f"{marker!r}"
                    )

    workflow_path = root / ".github" / "workflows" / "test.yml"
    try:
        workflow_text = workflow_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f".github/workflows/test.yml: cannot read: {exc}")
    else:
        if "scripts/smoke_compact_plus.py" not in workflow_text:
            errors.append(
                ".github/workflows/test.yml: synthetic smoke CLI must be py-compiled"
            )
    return errors


def validate_codex_compact_hook_assets(root):
    errors = []
    for relative in CODEX_COMPACT_HOOK_ASSETS:
        if not (root / relative).is_file():
            errors.append(f"{relative}: required Codex compact-hook asset is missing")
    hooks_path = root / "examples/codex/.codex/hooks.json"
    if hooks_path.is_file():
        try:
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"examples/codex/.codex/hooks.json: invalid JSON: {exc}")
            payload = {}
        hooks = payload.get("hooks") if isinstance(payload, dict) else None
        if not isinstance(hooks, dict):
            errors.append("examples/codex/.codex/hooks.json: hooks object is required")
        else:
            for event, matcher in CODEX_COMPACT_EVENTS.items():
                groups = hooks.get(event)
                if not isinstance(groups, list) or len(groups) != 1:
                    errors.append(f"examples/codex/.codex/hooks.json: {event} needs one group")
                    continue
                group = groups[0]
                if not isinstance(group, dict) or group.get("matcher") != matcher:
                    errors.append(
                        f"examples/codex/.codex/hooks.json: {event} matcher must be {matcher!r}"
                    )
                handlers = group.get("hooks") if isinstance(group, dict) else None
                command = handlers[0].get("command") if isinstance(handlers, list) and handlers else None
                if not isinstance(command, str) or ".codex/hooks/ascs_compact.py" not in command:
                    errors.append(
                        f"examples/codex/.codex/hooks.json: {event} must call the ASCS hook"
                    )
    script_path = root / "examples/codex/.codex/hooks/ascs_compact.py"
    if script_path.is_file():
        script = script_path.read_text(encoding="utf-8")
        for marker in (
            'event not in {"PreCompact", "PostCompact", "SessionStart"}',
            'payload.get("source") != "compact"',
            '"transcript_available"',
            "untrusted recovery context",
            'result = CONTINUE.copy()',
        ):
            if marker not in script:
                errors.append(
                    f"examples/codex/.codex/hooks/ascs_compact.py: missing safety marker {marker!r}"
                )
    docs_path = root / "docs/codex/adapter-design.md"
    if docs_path.is_file():
        docs = docs_path.read_text(encoding="utf-8")
        for marker in (
            "https://learn.chatgpt.com/docs/hooks",
            "retrieved 2026-07-16",
            "[Unverified]",
            "transcript format as unstable",
        ):
            if marker not in docs:
                errors.append(f"docs/codex/adapter-design.md: missing spec record {marker!r}")
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
            content_integrity = entry.get("content_integrity")
            if name in CONTENT_PINNED_UPSTREAMS:
                if (
                    not isinstance(content_integrity, dict)
                    or set(content_integrity)
                    != {"algorithm", "digest", "file_count", "verified_at"}
                    or content_integrity.get("algorithm") != "sha256-tree-v1"
                    or not TREE_SHA256.fullmatch(
                        str(content_integrity.get("digest", ""))
                    )
                    or isinstance(content_integrity.get("file_count"), bool)
                    or not isinstance(content_integrity.get("file_count"), int)
                    or not 0 < content_integrity["file_count"] <= 2048
                    or not ISO_DATE.fullmatch(
                        str(content_integrity.get("verified_at", ""))
                    )
                ):
                    errors.append(
                        f"config/upstreams.lock.json: invalid content integrity for {name}"
                    )
            elif content_integrity is not None:
                errors.append(
                    f"config/upstreams.lock.json: unexpected content integrity for {name}"
                )
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
            content_integrity = entry.get("content_integrity")
            if isinstance(content_integrity, dict):
                required_lock_tokens.extend(
                    str(content_integrity[key])
                    for key in ("algorithm", "digest", "file_count")
                    if content_integrity.get(key) is not None
                )
        for token in required_lock_tokens:
            if token not in policy_text:
                errors.append(
                    f"{update_policy}: does not document locked value {token}"
                )
    return errors


def validate_reviewed_plugin_snapshot(root):
    """Keep the Doctor's packaged version contract synced to the root lock."""
    lock_path = root / "config" / "upstreams.lock.json"
    snapshot_path = root / "plugins" / "ascs" / "reviewed-upstreams.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"plugins/ascs/reviewed-upstreams.json: cannot validate snapshot: {exc}"]

    errors = []
    if not isinstance(lock, dict) or not isinstance(lock.get("upstreams"), dict):
        return ["config/upstreams.lock.json: cannot derive reviewed plugin snapshot"]
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 2:
        return ["plugins/ascs/reviewed-upstreams.json: schema_version must be 2"]
    if snapshot.get("source") != "config/upstreams.lock.json":
        errors.append(
            "plugins/ascs/reviewed-upstreams.json: source must name config/upstreams.lock.json"
        )
    if snapshot.get("verified_at") != lock.get("verified_at"):
        errors.append(
            "plugins/ascs/reviewed-upstreams.json: verified_at must match the root lock"
        )
    plugins = snapshot.get("plugins")
    if not isinstance(plugins, dict) or set(plugins) != REVIEWED_PLUGIN_UPSTREAMS:
        return errors + [
            "plugins/ascs/reviewed-upstreams.json: plugin names must be exactly "
            + ", ".join(sorted(REVIEWED_PLUGIN_UPSTREAMS))
        ]

    upstreams = lock["upstreams"]
    for name in sorted(REVIEWED_PLUGIN_UPSTREAMS):
        snapshot_entry = plugins.get(name)
        lock_entry = upstreams.get(name)
        if not isinstance(snapshot_entry, dict) or not isinstance(lock_entry, dict):
            errors.append(
                f"plugins/ascs/reviewed-upstreams.json: {name} must match a lock object"
            )
            continue
        expected_fields = {"version", "revision"}
        if "content_integrity" in lock_entry:
            expected_fields.add("content_integrity")
        if set(snapshot_entry) != expected_fields:
            errors.append(
                "plugins/ascs/reviewed-upstreams.json: "
                f"{name} fields must be exactly {', '.join(sorted(expected_fields))}"
            )
        for field in ("version", "revision"):
            if snapshot_entry.get(field) != lock_entry.get(field):
                errors.append(
                    "plugins/ascs/reviewed-upstreams.json: "
                    f"{name}.{field} must match config/upstreams.lock.json"
                )
        if snapshot_entry.get("content_integrity") != lock_entry.get(
            "content_integrity"
        ):
            errors.append(
                "plugins/ascs/reviewed-upstreams.json: "
                f"{name}.content_integrity must match config/upstreams.lock.json"
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
    errors.extend(validate_implementation_status(root))
    errors.extend(validate_improvement_loop(root))
    errors.extend(validate_compact_plus_smoke_assets(root))
    errors.extend(validate_codex_compact_hook_assets(root))
    errors.extend(validate_upstream_lock(root, require=require_upstream_lock))
    errors.extend(validate_reviewed_plugin_snapshot(root))
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
    print(
        "Repository validation passed (JSON, manifests, links, doctor safety, "
        "implementation status, improvement loop, compact-plus synthetic smoke, "
        "Codex native compact hook, "
        "upstream lock, reviewed plugin snapshot, state trust)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
