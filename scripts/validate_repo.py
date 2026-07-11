#!/usr/bin/env python3
"""Dependency-free repository integrity checks used by local development and CI."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
GITHUB_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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

    errors = []
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        return ["config/upstreams.lock.json: schema_version must be 1"]
    upstreams = lock.get("upstreams")
    if not isinstance(upstreams, dict):
        return ["config/upstreams.lock.json: upstreams must be an object"]

    github_sources = {}
    npm_version = None
    for name, entry in upstreams.items():
        if not isinstance(entry, dict):
            errors.append(f"config/upstreams.lock.json: {name} must be an object")
            continue
        if entry.get("type") == "github":
            repo = entry.get("repo")
            revision = entry.get("revision")
            if not GITHUB_REPO.fullmatch(str(repo or "")) or not COMMIT_SHA.fullmatch(
                str(revision or "")
            ):
                errors.append(f"config/upstreams.lock.json: invalid GitHub lock for {name}")
            else:
                github_sources[repo] = revision
        elif entry.get("type") == "npm":
            version = entry.get("version")
            integrity = entry.get("integrity")
            if entry.get("package") != "pxpipe-proxy" or not SEMVER.fullmatch(
                str(version or "")
            ) or not str(integrity or "").startswith("sha512-"):
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

    if npm_version:
        markdown = "\n".join(
            path.read_text(encoding="utf-8")
            for path in root.rglob("*.md")
            if ".git" not in path.parts
        )
        if re.search(r"\bnpx\s+-y\s+pxpipe-proxy(?:\s|$)", markdown):
            errors.append("documentation contains an unpinned pxpipe-proxy invocation")
        if f"pxpipe-proxy@{npm_version}" not in markdown:
            errors.append("documentation does not reference the locked pxpipe-proxy version")
    return errors


def validate(root=REPO_ROOT, require_upstream_lock=False):
    root = Path(root).resolve()
    errors = []
    errors.extend(validate_json(root))
    errors.extend(validate_manifests(root))
    errors.extend(validate_internal_links(root))
    errors.extend(validate_doctor_command(root))
    errors.extend(validate_upstream_lock(root, require=require_upstream_lock))
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
    print("Repository validation passed (JSON, manifests, links, doctor safety, upstream lock when present).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
