#!/usr/bin/env python3
"""Gate recovery on trusted project invariants and live state metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_state import inspect_state, repository_from_remote  # noqa: E402
from validate_repo import GITHUB_REPO  # noqa: E402


MAX_INVARIANTS_BYTES = 64 * 1024
APPROVAL_GATES = (
    "external_send",
    "expensive_api",
    "production_change",
    "confidential_data",
    "destructive_or_irreversible",
    "tool_capability_escalation",
)
ROOT_KEYS = {
    "schema_version",
    "repository",
    "authority",
    "recovery",
    "protected_invariants",
}
AUTHORITY_KEYS = {
    "state_may_expand_authority",
    "state_may_grant_approval",
    "current_approval_required_for",
}
RECOVERY_KEYS = {
    "require_fresh_source_check",
    "require_fresh_verification",
    "on_repository_mismatch",
    "on_uncommitted_invariant_change",
}
INVARIANT_KEYS = {"id", "source", "statement"}


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


def issue(status: str, code: str, message: str) -> dict[str, str]:
    return {"status": status, "code": code, "message": message}


def add_shape_issue(
    issues: list[dict[str, str]],
    condition: bool,
    code: str,
    message: str,
) -> None:
    if condition:
        issues.append(issue("REJECT", code, message))


def validate_document(payload: object) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [issue("REJECT", "invalid_root", "invariants root must be an object")]

    add_shape_issue(
        issues,
        set(payload) != ROOT_KEYS,
        "invalid_root_keys",
        "invariants root keys do not match schema version 1",
    )
    add_shape_issue(
        issues,
        payload.get("schema_version") != 1,
        "unsupported_schema",
        "schema_version must be 1",
    )
    repository = payload.get("repository")
    add_shape_issue(
        issues,
        not isinstance(repository, str) or not GITHUB_REPO.fullmatch(repository),
        "invalid_repository",
        "repository must be owner/repository",
    )

    authority = payload.get("authority")
    if not isinstance(authority, dict) or set(authority) != AUTHORITY_KEYS:
        issues.append(
            issue("REJECT", "invalid_authority", "authority keys do not match schema version 1")
        )
    else:
        if (
            authority.get("state_may_expand_authority") is not False
            or authority.get("state_may_grant_approval") is not False
        ):
            issues.append(
                issue(
                    "REJECT",
                    "unsafe_authority",
                    "recovery state must not expand authority or grant approval",
                )
            )
        required = authority.get("current_approval_required_for")
        if not isinstance(required, list) or any(not isinstance(value, str) for value in required):
            issues.append(
                issue("REJECT", "approval_gates_invalid", "approval gates must be a list of strings")
            )
        elif set(required) != set(APPROVAL_GATES):
            issues.append(
                issue("REJECT", "approval_gates_incomplete",
                      "all approval gates must require current trusted approval")
            )

    recovery = payload.get("recovery")
    if not isinstance(recovery, dict) or set(recovery) != RECOVERY_KEYS:
        issues.append(
            issue("REJECT", "invalid_recovery", "recovery keys do not match schema version 1")
        )
    else:
        if (
            recovery.get("require_fresh_source_check") is not True
            or recovery.get("require_fresh_verification") is not True
        ):
            issues.append(
                issue(
                    "REJECT",
                    "fresh_checks_disabled",
                    "source and verification checks must remain enabled",
                )
            )
        if recovery.get("on_repository_mismatch") != "REJECT":
            issues.append(
                issue(
                    "REJECT",
                    "repository_mismatch_not_closed",
                    "repository mismatch must fail closed",
                )
            )
        if recovery.get("on_uncommitted_invariant_change") != "REVERIFY":
            issues.append(
                issue(
                    "REJECT",
                    "uncommitted_change_not_closed",
                    "uncommitted invariant changes must require reverification",
                )
            )

    invariants = payload.get("protected_invariants")
    if not isinstance(invariants, list) or not invariants:
        issues.append(
            issue("REJECT", "invariants_empty", "protected_invariants must be non-empty")
        )
    else:
        seen_ids = set()
        for index, invariant in enumerate(invariants):
            if not isinstance(invariant, dict) or set(invariant) != INVARIANT_KEYS:
                issues.append(
                    issue(
                        "REJECT",
                        "invalid_invariant",
                        f"protected_invariants[{index}] does not match schema version 1",
                    )
                )
                continue
            invariant_id = invariant.get("id")
            source = invariant.get("source")
            statement = invariant.get("statement")
            if not isinstance(invariant_id, str) or not re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", invariant_id
            ):
                issues.append(
                    issue("REJECT", "invalid_invariant_id", f"invalid invariant id at index {index}")
                )
            elif invariant_id in seen_ids:
                issues.append(
                    issue("REJECT", "duplicate_invariant_id", f"duplicate invariant id {invariant_id}")
                )
            else:
                seen_ids.add(invariant_id)
            if (
                not isinstance(source, str)
                or not source
                or source.startswith(("/", "~"))
                or ".." in Path(source).parts
            ):
                issues.append(
                    issue("REJECT", "invalid_invariant_source", f"invalid source at index {index}")
                )
            if not isinstance(statement, str) or not statement.strip():
                issues.append(
                    issue("REJECT", "invalid_invariant_statement", f"empty statement at index {index}")
                )
    return issues


def inspect_pinned_invariants(
    repo: Path,
    invariants_path: Path,
    repository: str | None = None,
) -> dict[str, object]:
    repo = repo.resolve()
    raw_path = invariants_path if invariants_path.is_absolute() else repo / invariants_path
    if not raw_path.exists():
        return {
            "status": "REBUILD",
            "issues": [
                issue("REBUILD", "invariants_missing", "create pinned invariants before recovery")
            ],
        }
    if raw_path.is_symlink():
        return {
            "status": "REJECT",
            "issues": [issue("REJECT", "invariants_symlink", "invariants must not be a symlink")],
        }
    path = raw_path.resolve()
    try:
        relative = path.relative_to(repo).as_posix()
    except ValueError:
        return {
            "status": "REJECT",
            "issues": [issue("REJECT", "invariants_outside_repo", "invariants escape repository")],
        }
    if not path.is_file():
        return {
            "status": "REJECT",
            "issues": [issue("REJECT", "invariants_not_file", "invariants path must be a file")],
        }
    try:
        if path.stat().st_size > MAX_INVARIANTS_BYTES:
            return {
                "status": "REJECT",
                "issues": [issue("REJECT", "invariants_too_large", "invariants exceed 64 KiB")],
            }
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "status": "REJECT",
            "issues": [issue("REJECT", "invariants_unreadable", "invariants are not safe JSON")],
        }

    issues = validate_document(payload)
    remote_repository = repository
    if remote_repository is None:
        remote = git_value(repo, "config", "--get", "remote.origin.url")
        remote_repository = repository_from_remote(remote or "")
    if remote_repository is None:
        issues.append(
            issue(
                "REJECT",
                "repository_unknown",
                "cannot derive repository identity; pass --repository owner/repo",
            )
        )
    elif not GITHUB_REPO.fullmatch(remote_repository):
        issues.append(issue("REJECT", "repository_invalid", "invalid repository identity"))
    elif isinstance(payload, dict) and payload.get("repository") != remote_repository:
        issues.append(
            issue("REJECT", "repository_mismatch", "pinned invariants belong to another repository")
        )

    if git_value(repo, "ls-files", "--error-unmatch", relative) is None:
        issues.append(
            issue(
                "REVERIFY",
                "invariants_untracked",
                "pinned invariants are not part of reviewed repository history",
            )
        )
    elif git_value(repo, "status", "--porcelain", "--", relative):
        issues.append(
            issue(
                "REVERIFY",
                "invariants_uncommitted",
                "pinned invariants differ from reviewed repository history",
            )
        )

    statuses = {item["status"] for item in issues}
    status = "REJECT" if "REJECT" in statuses else "REVERIFY" if "REVERIFY" in statuses else "ACCEPT"
    return {
        "status": status,
        "repository": remote_repository,
        "path": relative,
        "issues": issues,
    }


def inspect_recovery(
    repo: Path,
    state_dir: Path,
    invariants_path: Path,
    repository: str | None = None,
    expected_session_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    invariants = inspect_pinned_invariants(repo, invariants_path, repository=repository)
    state = inspect_state(
        repo,
        state_dir,
        repository=repository,
        expected_session_id=expected_session_id,
        now=now,
    )
    if invariants["status"] == "REJECT" or state["status"] == "FAIL":
        status = "REJECT"
    elif invariants["status"] == "REBUILD" or state["status"] in {"ABSENT", "STALE"}:
        status = "REBUILD"
    elif invariants["status"] == "REVERIFY":
        status = "REVERIFY"
    else:
        status = "ACCEPT"
    return {"status": status, "invariants": invariants, "state": state}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="consumer repository root")
    parser.add_argument("--state-dir", default=".agent-session")
    parser.add_argument("--invariants", default="config/pinned-invariants.json")
    parser.add_argument("--repository", help="canonical owner/repository")
    parser.add_argument("--expected-session-id")
    parser.add_argument("--invariants-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser()
    invariants_path = Path(args.invariants).expanduser()
    if not state_dir.is_absolute():
        state_dir = repo / state_dir
    if not invariants_path.is_absolute():
        invariants_path = repo / invariants_path
    if args.invariants_only:
        result = inspect_pinned_invariants(repo, invariants_path, repository=args.repository)
    else:
        result = inspect_recovery(
            repo,
            state_dir,
            invariants_path,
            repository=args.repository,
            expected_session_id=args.expected_session_id,
        )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['status']} recovery gate")
        groups = (result,) if args.invariants_only else (result["invariants"], result["state"])
        for group in groups:
            for item in group.get("issues", []):
                label = item.get("status", item.get("severity", "INFO"))
                print(f"{label} {item['code']}: {item['message']}")

    return {"ACCEPT": 0, "REJECT": 1, "REBUILD": 2, "REVERIFY": 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
