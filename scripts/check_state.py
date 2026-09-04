#!/usr/bin/env python3
"""Check live .agent-session trust metadata before reading recovery content."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from validate_repo import (
    COMMIT_SHA,
    GITHUB_REPO,
    STATE_METADATA_KEYS,
    parse_state_metadata,
    parse_iso_datetime,
)


MAX_STATE_FILE_BYTES = 256 * 1024


def git_value(repo: Path, *args: str) -> str | None:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def repository_from_remote(remote: str) -> str | None:
    value = remote.strip()
    scp_match = re.match(r"^[^@]+@[^:]+:(?P<path>.+)$", value)
    if scp_match:
        path = scp_match.group("path")
    else:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https", "ssh", "git"):
            return None
        path = parsed.path
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    repository = "/".join(parts[-2:])
    if repository.endswith(".git"):
        repository = repository[:-4]
    return repository if GITHUB_REPO.fullmatch(repository) else None


def issue(severity: str, code: str, message: str, path: str | None = None) -> dict[str, str]:
    result = {"severity": severity, "code": code, "message": message}
    if path is not None:
        result["path"] = path
    return result


def read_state_files(repo: Path, relative_state: Path):
    """Read through pinned directory descriptors; never follow state links.

    O_NONBLOCK prevents a swapped-in FIFO from waiting for a writer. fstat
    validates the opened file, and the bounded read also catches file growth.
    """
    files = {}
    issues = []
    if not all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
        return {}, [issue("FAIL", "state_io_unsupported", "safe state inspection requires POSIX file operations")], False
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    def failure(code, message, path):
        issues.append(issue("FAIL", code, message, path.as_posix()))

    def scan(directory_fd, relative):
        try:
            with os.scandir(directory_fd) as entries:
                names = sorted(entry.name for entry in entries)
            for name in names:
                path = relative / name
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    failure("state_symlink", "state paths must not be symbolic links", path)
                elif stat.S_ISDIR(info.st_mode):
                    if name == ".rollback":
                        continue
                    if path.suffix == ".md":
                        failure("state_not_file", "state must be a regular file", path)
                        continue
                    child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                    try:
                        scan(child_fd, path)
                    finally:
                        os.close(child_fd)
                elif path.suffix == ".md":
                    if not stat.S_ISREG(info.st_mode):
                        failure("state_not_file", "state must be a regular file", path)
                        continue
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=directory_fd)
                    with os.fdopen(fd, "rb") as handle:
                        opened = os.fstat(handle.fileno())
                        if not stat.S_ISREG(opened.st_mode):
                            failure("state_not_file", "state must be a regular file", path)
                            continue
                        if opened.st_size > MAX_STATE_FILE_BYTES:
                            failure("state_too_large", "state file exceeds 256 KiB", path)
                            continue
                        data = handle.read(MAX_STATE_FILE_BYTES + 1)
                    if len(data) > MAX_STATE_FILE_BYTES:
                        failure("state_too_large", "state file exceeds 256 KiB", path)
                        continue
                    try:
                        files[repo / path] = data.decode("utf-8")
                    except UnicodeError:
                        failure("state_unreadable", "state file is not UTF-8", path)
        except OSError:
            failure("state_unreadable", "state directory cannot be inspected safely", relative)

    directory_fd = None
    try:
        directory_fd = os.open(repo, directory_flags)
        for part in relative_state.parts:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        scan(directory_fd, relative_state)
    except FileNotFoundError:
        return {}, [], True
    except (OSError, AttributeError, NotImplementedError):
        failure("state_unreadable", "state path cannot be inspected without following links", relative_state)
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    return files, issues, False


def inspect_state(
    repo: Path,
    state_dir: Path,
    repository: str | None = None,
    expected_session_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    raw_repo = repo.absolute()
    raw_state = state_dir if state_dir.is_absolute() else raw_repo / state_dir
    repo = repo.resolve()
    try:
        # Keep the state path lexical so in-repo links cannot disappear during resolve.
        anchor = raw_repo if raw_state.is_relative_to(raw_repo) else repo
        relative_state = raw_state.relative_to(anchor)
        if ".." in relative_state.parts:
            raise ValueError("state path contains parent traversal")
    except ValueError:
        return {
            "status": "FAIL",
            "issues": [issue("FAIL", "state_outside_repo", "state directory escapes repository")],
        }
    files, scan_issues, absent = read_state_files(repo, relative_state)
    if absent or (not files and not scan_issues):
        return {"status": "ABSENT", "issues": [], "files_checked": 0}

    branch = git_value(repo, "branch", "--show-current")
    commit = git_value(repo, "rev-parse", "HEAD")
    if repository is None:
        remote = git_value(repo, "config", "--get", "remote.origin.url")
        repository = repository_from_remote(remote or "")
    context_issues = list(scan_issues)
    if repository is None:
        context_issues.append(
            issue(
                "FAIL",
                "repository_unknown",
                "cannot derive canonical repository identity; pass --repository owner/repo",
            )
        )
    elif not GITHUB_REPO.fullmatch(repository):
        context_issues.append(issue("FAIL", "repository_invalid", "invalid repository identity"))
    if not branch:
        context_issues.append(issue("FAIL", "branch_unknown", "cannot determine current branch"))
    if not commit or not COMMIT_SHA.fullmatch(commit):
        context_issues.append(issue("FAIL", "commit_unknown", "cannot determine current commit"))

    metadata_entries: list[tuple[str, dict[str, str]]] = []
    now = now or datetime.now(timezone.utc)
    for path, text in sorted(files.items()):
        relative = path.relative_to(repo).as_posix()
        metadata, errors = parse_state_metadata(path, repo, text=text)
        for error in errors:
            context_issues.append(issue("FAIL", "metadata_invalid", error, relative))
        if re.search(
            r"(?:/Users/|/home/|/private/var/|/var/folders/|/tmp/|~/\.|[A-Za-z]:[\\/]+Users[\\/])",
            text,
        ):
            context_issues.append(
                issue("FAIL", "machine_path", "machine-specific absolute path detected", relative)
            )
        if re.search(r"(?i)\b(?:sha(?:1|256|512)|machine_id|hostname)\s*[:=]", text):
            context_issues.append(
                issue("FAIL", "fingerprint", "machine/content fingerprint detected", relative)
            )
        if "-----BEGIN " in text and "PRIVATE KEY-----" in text:
            context_issues.append(issue("FAIL", "private_key", "private key material detected", relative))
        if re.search(
            r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*(?!<|redacted|\*{3})\S+",
            text,
        ):
            context_issues.append(
                issue("FAIL", "secret_value", "apparent secret value detected", relative)
            )
        if metadata is None or errors:
            continue
        if any(metadata[key].startswith("<") for key in STATE_METADATA_KEYS):
            context_issues.append(
                issue("FAIL", "metadata_placeholder", "live state contains metadata placeholders", relative)
            )
            continue
        metadata_entries.append((relative, metadata))
        if metadata["state_schema_version"] != "1":
            context_issues.append(issue("FAIL", "schema_mismatch", "unsupported state schema", relative))
        if not GITHUB_REPO.fullmatch(metadata["repository"]):
            context_issues.append(
                issue("FAIL", "state_repository_invalid", "invalid state repository identity", relative)
            )
        if not metadata["branch"] or "\0" in metadata["branch"]:
            context_issues.append(issue("FAIL", "state_branch_invalid", "invalid state branch", relative))
        if not COMMIT_SHA.fullmatch(metadata["commit"]):
            context_issues.append(
                issue("FAIL", "state_commit_invalid", "state commit must be a 40-character SHA", relative)
            )
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", metadata["session_id"]):
            context_issues.append(
                issue("FAIL", "state_session_invalid", "invalid state session identifier", relative)
            )
        if repository is not None and metadata["repository"] != repository:
            context_issues.append(
                issue("FAIL", "repository_mismatch", "ignore the entire state set", relative)
            )
        if branch and metadata["branch"] != branch:
            context_issues.append(
                issue("STALE", "branch_mismatch", "state branch differs from current branch", relative)
            )
        if commit and metadata["commit"] != commit:
            context_issues.append(
                issue("STALE", "commit_mismatch", "state commit differs from current HEAD", relative)
            )
        if expected_session_id and metadata["session_id"] != expected_session_id:
            context_issues.append(
                issue("STALE", "session_mismatch", "state was written by another session", relative)
            )
        try:
            updated = parse_iso_datetime(metadata["updated_at"])
            expires = parse_iso_datetime(metadata["expires_at"])
            if updated.tzinfo is None or expires.tzinfo is None:
                raise ValueError("timezone required")
            if not updated < expires <= updated + timedelta(days=7):
                context_issues.append(
                    issue("FAIL", "invalid_retention", "expiry must be within seven days", relative)
                )
            if updated > now + timedelta(minutes=5):
                context_issues.append(
                    issue("FAIL", "future_state", "state update time is in the future", relative)
                )
            if expires <= now:
                context_issues.append(issue("STALE", "expired", "state has expired", relative))
        except ValueError:
            context_issues.append(issue("FAIL", "invalid_time", "invalid ISO-8601 state time", relative))

    identity_keys = ("state_schema_version", "repository", "branch", "commit", "session_id")
    if metadata_entries:
        expected = tuple(metadata_entries[0][1][key] for key in identity_keys)
        for relative, metadata in metadata_entries[1:]:
            actual = tuple(metadata[key] for key in identity_keys)
            if actual != expected:
                context_issues.append(
                    issue("FAIL", "split_state", "state identity metadata disagrees across files", relative)
                )

    severities = {item["severity"] for item in context_issues}
    status = "FAIL" if "FAIL" in severities else "STALE" if "STALE" in severities else "PASS"
    return {
        "status": status,
        "repository": repository,
        "branch": branch,
        "commit": commit,
        "files_checked": len(files),
        "issues": context_issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="consumer repository root")
    parser.add_argument(
        "--state-dir", default=".agent-session", help="state directory inside the repository"
    )
    parser.add_argument(
        "--repository", help="canonical owner/repository when origin cannot be derived"
    )
    parser.add_argument(
        "--expected-session-id", help="optional same-session writer check"
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser()
    if not state_dir.is_absolute():
        state_dir = repo / state_dir
    result = inspect_state(
        repo,
        state_dir,
        repository=args.repository,
        expected_session_id=args.expected_session_id,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['status']} state trust check ({result.get('files_checked', 0)} files)")
        for item in result.get("issues", []):
            location = f" {item['path']}:" if item.get("path") else ""
            print(f"{item['severity']}{location} {item['code']}: {item['message']}")
    return 1 if result["status"] == "FAIL" else 2 if result["status"] == "STALE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
