#!/usr/bin/env python3
"""Operator helper for Experiment 004.

This helper prepares isolated target-repo checkouts and records manual
Experiment 004 events through scripts/ascs.py. It never starts Claude Code,
pushes, opens PRs or issues, tags releases, or writes experiment events
directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SANDBOX_ROOT = "~/projects/_sandbox/ascs-exp004"
MARKER_BEGIN = "<!-- BEGIN ASCS EXPERIMENT SCAFFOLDING (exp-004) - do not commit -->"
MARKER_END = "<!-- END ASCS EXPERIMENT SCAFFOLDING (exp-004) -->"
REQUIRED_STATE_FILES = [
    "handoff.md",
    "state/current-plan.md",
    "state/decision-log.md",
    "state/failed-attempts.md",
    "state/checkpoint.md",
    "state/recovery-notes.md",
]
VOID_CONDITIONS = ("1a", "1b", "2", "3", "4", "5", "6")
FROZEN_SHARED_SCAFFOLD = (
    "experiments/2026-07-06-claude-code-restart-004-shared-scaffold/.agent-session"
)
DISABLED_PUSH_URL = "file:///__ascs_exp004_push_disabled__"


@dataclass(frozen=True)
class Arm:
    name: str
    experiment_dir: str
    task: str
    condition: str
    order: int
    pair: str
    branch: str


ARMS = {
    "004-p1-baseline": Arm(
        name="004-p1-baseline",
        experiment_dir="experiments/2026-07-06-claude-code-restart-004-p1-baseline",
        task="T-A rename tracking + extension_in_public",
        condition="baseline",
        order=1,
        pair="1",
        branch="exp-004-p1-baseline",
    ),
    "004-p1-treated": Arm(
        name="004-p1-treated",
        experiment_dir="experiments/2026-07-06-claude-code-restart-004-p1-treated",
        task="T-A rename tracking + extension_in_public",
        condition="treated",
        order=2,
        pair="1",
        branch="exp-004-p1-treated",
    ),
    "004-p2-treated": Arm(
        name="004-p2-treated",
        experiment_dir="experiments/2026-07-06-claude-code-restart-004-p2-treated",
        task="T-B CTAS modeling + Splinter 0004 no_primary_key",
        condition="treated",
        order=3,
        pair="2",
        branch="exp-004-p2-treated",
    ),
    "004-p2-baseline": Arm(
        name="004-p2-baseline",
        experiment_dir="experiments/2026-07-06-claude-code-restart-004-p2-baseline",
        task="T-B CTAS modeling + Splinter 0004 no_primary_key",
        condition="baseline",
        order=4,
        pair="2",
        branch="exp-004-p2-baseline",
    ),
}

PAIR_ARMS = {
    "1": ("004-p1-baseline", "004-p1-treated"),
    "2": ("004-p2-treated", "004-p2-baseline"),
}

TASK_TEXT = {
    "1": """T-A has two slices.

Slice 1: model `ALTER POLICY ... RENAME TO`.
- Add the statement type, parser extraction in both backends, schema-state
  folding, and tests.
- Acceptance assertions: after a rename, an `ALTER POLICY` patch addressed
  to the new name applies; a patch addressed to the old name fails
  conservative; findings report the current name; libpg and regex agree.
- Commit Slice 1 once its tests and the full suite are green.

Slice 2: add `extension_in_public` (target repo ID candidate RLS019).
- After the Slice 1 commit, write the new failing tests first.
- Stop after the Slice 2 tests are present, uncommitted, failing, and no
  Slice 2 implementation files have been edited.
- Do not implement Slice 2 before stopping.""",
    "2": """T-B has two slices.

Slice 1: model `CREATE TABLE AS`.
- Fold the CTAS table into schema state so table-level rules apply, mark
  its column list unknown, and make column-level rules skip it without
  crashing or false positives; both parser backends; tests.
- Acceptance assertions: a CTAS table without RLS enabled is flagged by
  RLS-enablement rules; column-level rules neither fire nor crash on it;
  both backends agree.
- Commit Slice 1 once its tests and the full suite are green.

Slice 2: add Splinter 0004 `no_primary_key` (target repo ID candidate
RLS020).
- The checkpoint failing tests must use ordinary `CREATE TABLE` statements
  without a primary key.
- Do not exercise a CTAS-created table in the checkpoint failing tests.
- Leave the CTAS/no_primary_key interaction as a resumed-session design
  decision.
- After the Slice 1 commit, write the new failing tests first.
- Stop after the Slice 2 tests are present, uncommitted, failing, and no
  Slice 2 implementation files have been edited.
- Do not implement Slice 2 before stopping.""",
}


def ascs_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAIL {message}", file=sys.stderr)
    return 1


def run_cmd(cmd: list[str], cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )


def run_git(repo: Path, args: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run_cmd(["git"] + args, repo, capture=capture)


def require_success(proc: subprocess.CompletedProcess[str], command_text: str) -> bool:
    if proc.returncode == 0:
        return True
    if proc.stdout:
        print(proc.stdout, end="", file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    print(f"FAIL command failed: {command_text}", file=sys.stderr)
    return False


def arm_from_name(name: str) -> Arm:
    return ARMS[name]


def experiment_path(arm: Arm) -> Path:
    return ascs_root() / arm.experiment_dir


def events_path(arm: Arm) -> Path:
    return experiment_path(arm) / "events.jsonl"


def sandbox_root(path_text: str = DEFAULT_SANDBOX_ROOT) -> Path:
    return Path(path_text).expanduser().resolve()


def checkout_path(arm: Arm, root: Path) -> Path:
    return root / arm.name / "supabase-rls-guard"


def ensure_git_worktree(path: Path, label: str) -> int:
    if not path.exists():
        return fail(f"{label} does not exist: {path}")
    proc = run_git(path, ["rev-parse", "--is-inside-work-tree"], capture=True)
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return fail(f"{label} is not a git work tree: {path}")
    return 0


def ensure_clean(repo: Path) -> int:
    proc = run_git(
        repo,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture=True,
    )
    if proc.returncode != 0:
        return fail(f"could not inspect working tree: {repo}")
    entries = parse_porcelain_z(proc.stdout)
    if entries:
        for status, path in entries:
            print(f"{status} {path}", file=sys.stderr)
        return fail(f"working tree is not clean: {repo}")
    return 0


def parse_porcelain_z(output: str) -> list[tuple[str, str]]:
    """Parse `git status --porcelain=v1 -z`, including rename source paths."""
    tokens = output.split("\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(tokens):
        record = tokens[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise ValueError(f"malformed porcelain v1 -z record: {record!r}")
        status, path = record[:2], record[3:]
        entries.append((status, path))
        if "R" in status or "C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise ValueError("rename/copy porcelain record is missing its source path")
            entries.append((status, tokens[index]))
            index += 1
    return entries


def disable_push_remotes(checkout: Path) -> int:
    """Make every cloned remote non-pushable and disable implicit pushes."""
    remotes_proc = run_git(checkout, ["remote"], capture=True)
    if remotes_proc.returncode != 0:
        return fail("could not enumerate experiment remotes")
    remotes = [line.strip() for line in remotes_proc.stdout.splitlines() if line.strip()]
    if not remotes:
        return fail("experiment checkout has no remote to disable")
    for remote in remotes:
        proc = run_git(checkout, ["remote", "set-url", "--push", remote, DISABLED_PUSH_URL])
        if proc.returncode != 0:
            return fail(f"could not disable push URL for remote {remote}")
    proc = run_git(checkout, ["config", "push.default", "nothing"])
    if proc.returncode != 0:
        return fail("could not disable implicit git push")
    for remote in remotes:
        proc = run_git(checkout, ["remote", "get-url", "--push", remote], capture=True)
        if proc.returncode != 0 or proc.stdout.strip() != DISABLED_PUSH_URL:
            return fail(f"push URL verification failed for remote {remote}")
    return 0


def prepare_recovery_packet(arm: Arm, checkout: Path, base_hash: str, stage: str) -> str:
    checkout_arg = shlex.quote(str(checkout))
    return "\n".join(
        (
            "PREPARE RECOVERY (no automatic cleanup performed)",
            f"arm: {arm.name}",
            f"failed stage: {stage}",
            f"requested base: {base_hash}",
            f"partial checkout: {checkout}",
            "source repository was not modified by prepare-arm",
            f"inspect: git -C {checkout_arg} status --short --branch",
            "after inspection, preserve useful work or remove the partial checkout manually",
        )
    )


def fail_prepare(arm: Arm, checkout: Path, base_hash: str, stage: str) -> int:
    print(prepare_recovery_packet(arm, checkout, base_hash, stage), file=sys.stderr)
    return 1


def resolve_commit(repo: Path, commit: str) -> tuple[str | None, int]:
    proc = run_git(repo, ["rev-parse", "--verify", f"{commit}^{{commit}}"], capture=True)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        return None, fail(f"base commit does not exist: {commit}")
    return proc.stdout.strip(), 0


def load_events(arm: Arm) -> list[dict[str, object]]:
    path = events_path(arm)
    events: list[dict[str, object]] = []
    if not path.exists():
        return events
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if isinstance(event, dict):
            events.append(event)
    return events


def has_event(arm: Arm, event_name: str) -> bool:
    return any(event.get("event") == event_name for event in load_events(arm))


def last_event_name(arm: Arm) -> str | None:
    events = load_events(arm)
    if not events:
        return None
    return str(events[-1].get("event"))


def arm_start_base(arm: Arm) -> str | None:
    for event in load_events(arm):
        if event.get("event") != "arm_start":
            continue
        note = str(event.get("note", ""))
        match = re.search(r"\bbase commit: ([0-9a-f]{40})\b", note)
        if match:
            return match.group(1)
    return None


def run_ascs(args: list[str]) -> int:
    proc = run_cmd(["python3", "scripts/ascs.py"] + args, ascs_root())
    return proc.returncode


def record_event(
    arm: Arm,
    event_name: str,
    note: str,
    *,
    pair_id: str | None = None,
    condition: str | None = None,
    transaction_id: str | None = None,
) -> int:
    command = [
        "record",
        "--experiment",
        arm.experiment_dir,
        "--event",
        event_name,
        "--note",
        note,
    ]
    for flag, value in (
        ("--pair-id", pair_id),
        ("--condition", condition),
        ("--transaction-id", transaction_id),
    ):
        if value is not None:
            command.extend((flag, value))
    return run_ascs(command)


def event_note_field(event: dict[str, object], field: str) -> str | None:
    note = str(event.get("note", ""))
    match = re.search(rf"(?:^|;\s*){re.escape(field)}=([^;]+)", note)
    return match.group(1).strip() if match else None


def transaction_event_ids(
    arm: Arm, event_name: str, target_event: str | None = None
) -> set[str]:
    transaction_ids = set()
    for event in load_events(arm):
        if event.get("event") != event_name:
            continue
        if target_event is not None and event_note_field(event, "target_event") != target_event:
            continue
        transaction_id = event_note_field(event, "txid")
        if transaction_id:
            transaction_ids.add(transaction_id)
    return transaction_ids


def arm_has_transaction_stage(
    arm: Arm, event_name: str, transaction_id: str, target_event: str | None = None
) -> bool:
    return transaction_id in transaction_event_ids(arm, event_name, target_event)


def transaction_stage_notes(
    arm: Arm, event_name: str, transaction_id: str, target_event: str | None = None
) -> list[str]:
    notes = []
    for event in load_events(arm):
        if event.get("event") != event_name:
            continue
        if event_note_field(event, "txid") != transaction_id:
            continue
        if target_event is not None and event_note_field(event, "target_event") != target_event:
            continue
        notes.append(str(event.get("note", "")))
    return notes


def pair_event_committed(pair: str, event_name: str) -> bool:
    arms = [arm_from_name(name) for name in PAIR_ARMS[pair]]
    if all(
        any(
            event.get("event") == event_name and event_note_field(event, "txid") is None
            for event in load_events(arm)
        )
        for arm in arms
    ):
        return True

    committed_ids: set[str] | None = None
    for arm in arms:
        arm_ids = transaction_event_ids(arm, event_name)
        arm_ids &= transaction_event_ids(arm, "pair-event-commit", event_name)
        committed_ids = arm_ids if committed_ids is None else committed_ids & arm_ids
    return bool(committed_ids)


def pair_event_pending(pair: str, event_name: str) -> bool:
    arms = [arm_from_name(name) for name in PAIR_ARMS[pair]]
    untagged = [
        any(
            event.get("event") == event_name and event_note_field(event, "txid") is None
            for event in load_events(arm)
        )
        for arm in arms
    ]
    if any(untagged) and not all(untagged):
        return True

    transaction_ids = set()
    for arm in arms:
        transaction_ids |= transaction_event_ids(arm, event_name)
        for stage in ("pair-event-prepare", "pair-event-commit", "pair-event-abort"):
            transaction_ids |= transaction_event_ids(arm, stage, event_name)
    for transaction_id in transaction_ids:
        if not all(
            arm_has_transaction_stage(arm, event_name, transaction_id)
            and arm_has_transaction_stage(
                arm, "pair-event-commit", transaction_id, event_name
            )
            for arm in arms
        ):
            return True
    return False


def record_pair_event(
    pair: str, event_name: str, note: str, transaction_id: str
) -> int:
    """Idempotently record a pair event with prepare/commit recovery markers."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", transaction_id):
        return fail("pair transaction ID contains unsupported characters")
    arms = [arm_from_name(name) for name in PAIR_ARMS[pair]]
    stage_notes = (
        (
            "pair-event-prepare",
            f"txid={transaction_id}; pair={pair}; target_event={event_name}",
        ),
        (event_name, f"{note}; txid={transaction_id}"),
        (
            "pair-event-commit",
            f"txid={transaction_id}; pair={pair}; target_event={event_name}",
        ),
    )
    for stage_name, stage_note in stage_notes:
        target_filter = event_name if stage_name.startswith("pair-event-") else None
        for arm in arms:
            existing_notes = transaction_stage_notes(
                arm, stage_name, transaction_id, target_filter
            )
            if existing_notes:
                if any(existing_note != stage_note for existing_note in existing_notes):
                    return fail(
                        f"pair transaction payload mismatch for {arm.name}/{stage_name}"
                    )
                continue
            if record_event(
                arm,
                stage_name,
                stage_note,
                pair_id=pair,
                condition=arm.condition,
                transaction_id=transaction_id,
            ):
                abort_note = (
                    f"txid={transaction_id}; pair={pair}; target_event={event_name}; "
                    f"failed_stage={stage_name}"
                )
                for abort_arm in arms:
                    if not arm_has_transaction_stage(
                        abort_arm, "pair-event-abort", transaction_id, event_name
                    ):
                        if record_event(
                            abort_arm,
                            "pair-event-abort",
                            abort_note,
                            pair_id=pair,
                            condition=abort_arm.condition,
                            transaction_id=transaction_id,
                        ):
                            print(
                                f"WARN could not record abort marker for {abort_arm.name}",
                                file=sys.stderr,
                            )
                print(
                    "PAIR EVENT RECOVERY: no pair claim is committed; fix the event "
                    f"writer and retry the same command (txid={transaction_id})",
                    file=sys.stderr,
                )
                return 1
    print(f"PASS committed pair event {event_name} ({transaction_id})")
    return 0


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scaffold_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def scaffold_tree_hash(root: Path) -> str:
    file_hashes = scaffold_file_hashes(root)
    payload = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def maybe_project_state_warning(checkout: Path) -> str:
    projects_dir = Path("~/.claude/projects").expanduser()
    if not projects_dir.exists():
        return "claude project state dir missing"
    encoded = str(checkout).replace("/", "-")
    matches = [path.name for path in projects_dir.iterdir() if encoded in path.name]
    if matches:
        return "exact project state match detected: " + ", ".join(sorted(matches))
    return "no exact project state match detected"


def frozen_shared_scaffold_path() -> Path:
    return ascs_root() / FROZEN_SHARED_SCAFFOLD


def verify_frozen_shared_scaffold() -> int:
    source = frozen_shared_scaffold_path()
    if not source.is_dir():
        return fail(f"frozen shared scaffold is missing: {source}")
    missing = [path for path in REQUIRED_STATE_FILES if not (source / path).is_file()]
    if missing:
        return fail("frozen shared scaffold is missing files: " + ", ".join(missing))
    return 0


def setup_treated(checkout: Path) -> int:
    claude_path = checkout / "CLAUDE.md"
    content = claude_path.read_text(encoding="utf-8") if claude_path.exists() else ""
    if MARKER_BEGIN in content or MARKER_END in content:
        return fail("target CLAUDE.md already contains an exp-004 ASCS marker")
    session_dir = checkout / ".agent-session"
    if session_dir.exists():
        return fail(
            "treated target repo already contains .agent-session/; "
            "contamination risk, preserving existing files as evidence"
        )
    if verify_frozen_shared_scaffold():
        return 1
    if not claude_path.exists():
        claude_path.write_text("# CLAUDE.md\n", encoding="utf-8")
        content = claude_path.read_text(encoding="utf-8")
    scaffold = (ascs_root() / "examples/claude-code/stack-demo/CLAUDE.md.example").read_text(
        encoding="utf-8"
    )
    with claude_path.open("a", encoding="utf-8") as f:
        if content and not content.endswith("\n"):
            f.write("\n")
        f.write("\n")
        f.write(MARKER_BEGIN)
        f.write("\n")
        f.write(scaffold.rstrip())
        f.write("\n")
        f.write(MARKER_END)
        f.write("\n")

    shutil.copytree(frozen_shared_scaffold_path(), session_dir)
    return verify_treated_setup(checkout)


def verify_baseline_setup(checkout: Path) -> int:
    claude_path = checkout / "CLAUDE.md"
    if claude_path.exists():
        content = claude_path.read_text(encoding="utf-8")
        if MARKER_BEGIN in content or MARKER_END in content:
            return fail("baseline target CLAUDE.md contains an exp-004 ASCS marker")
    if (checkout / ".agent-session").exists():
        return fail("baseline target repo contains .agent-session/")
    return 0


def verify_treated_setup(checkout: Path) -> int:
    claude_path = checkout / "CLAUDE.md"
    if not claude_path.exists():
        return fail("treated setup requires CLAUDE.md")
    content = claude_path.read_text(encoding="utf-8")
    if content.count(MARKER_BEGIN) != 1 or content.count(MARKER_END) != 1:
        return fail("treated CLAUDE.md must contain exactly one exp-004 marker block")
    session_dir = checkout / ".agent-session"
    missing = [path for path in REQUIRED_STATE_FILES if not (session_dir / path).exists()]
    if missing:
        return fail("treated .agent-session/ is missing files: " + ", ".join(missing))
    source_hash = scaffold_tree_hash(frozen_shared_scaffold_path())
    dest_hash = scaffold_tree_hash(session_dir)
    if source_hash != dest_hash:
        return fail(
            "treated .agent-session/ hash does not match frozen shared scaffold: "
            f"source={source_hash} dest={dest_hash}"
        )
    return 0


def isolation_setup_note(arm: Arm, checkout: Path, base_hash: str) -> str:
    note = (
        f"isolation-setup; checkout_id: {arm.name}; base commit: {base_hash}; "
        "machine path and environment fingerprints omitted"
    )
    if arm.condition == "treated":
        note += "; frozen and copied scaffolds verified equal locally; hashes omitted"
    return note


def build_prompt(arm: Arm, phase: str) -> str:
    task_text = TASK_TEXT[arm.pair]
    if phase == "first":
        return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

Experiment 004 の作業セッションです。
repo: supabase-rls-guard

制約:
- repo の通常の開発指示を読んで従ってください。
- push / release / issue / PR は作成しないでください。
- 他の AI のレビュー・支援は使わないでください。

Task:
{task_text}

Work order:
- Complete Slice 1 first.
- Commit Slice 1 only after its tests and the full suite are green.
- Then write Slice 2 tests first.
- Run the suite and confirm only the new Slice 2 tests fail.
- Report and wait before editing any Slice 2 implementation file.
"""

    return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

前回の fresh session は checkpoint で終了しました。同じタスクを完了してください。

Task:
{task_text}

Done definition:
- Complete the remaining Slice 2 implementation.
- Keep both parser backends consistent where the task requires parity.
- Update the relevant docs and rule count when the task requires it.
- Run the final relevant suite and report the result.
- Do not push, release, create issues, create PRs, or use other AI help.
"""


def changed_files(checkout: Path) -> list[str]:
    proc = run_git(
        checkout,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "git status failed")
    return list(dict.fromkeys(path for _status, path in parse_porcelain_z(proc.stdout)))


def committed_scaffold_contamination(checkout: Path, base_hash: str) -> list[str]:
    contaminated: list[str] = []
    state_proc = run_git(
        checkout,
        ["diff", "--name-only", "-z", f"{base_hash}..HEAD", "--", ".agent-session"],
        capture=True,
    )
    if state_proc.returncode != 0:
        raise RuntimeError(state_proc.stderr or "git diff for committed state failed")
    contaminated.extend(path for path in state_proc.stdout.split("\0") if path)

    claude_diff = run_git(
        checkout,
        ["diff", "--name-only", "-z", f"{base_hash}..HEAD", "--", "CLAUDE.md"],
        capture=True,
    )
    if claude_diff.returncode != 0:
        raise RuntimeError(claude_diff.stderr or "git diff for committed CLAUDE.md failed")
    if claude_diff.stdout.strip("\0"):
        content_proc = run_git(checkout, ["show", "HEAD:CLAUDE.md"], capture=True)
        if content_proc.returncode == 0 and (
            MARKER_BEGIN in content_proc.stdout or MARKER_END in content_proc.stdout
        ):
            contaminated.append("CLAUDE.md (exp-004 marker)")
    return contaminated


def is_test_file(path: str) -> bool:
    return path.startswith("tests/") or "/tests/" in path or path.endswith("_test.go") or path.endswith(".test.ts")


def allowed_checkpoint_file(path: str, arm: Arm) -> bool:
    if is_test_file(path):
        return True
    if arm.condition == "treated" and (
        path == "CLAUDE.md" or path.startswith(".agent-session/")
    ):
        return True
    return False


def checkpoint_signature(arm: Arm, checkout: Path) -> tuple[dict[str, object] | None, int]:
    if ensure_git_worktree(checkout, "arm checkout"):
        return None, 1
    base_hash = arm_start_base(arm)
    if base_hash is None:
        return None, fail(f"{arm.name} has no arm_start event with base commit")
    head_proc = run_git(checkout, ["rev-parse", "HEAD"], capture=True)
    if head_proc.returncode != 0:
        return None, fail("could not resolve HEAD")
    head = head_proc.stdout.strip()
    try:
        committed_contamination = committed_scaffold_contamination(checkout, base_hash)
    except RuntimeError as exc:
        return None, fail(str(exc))
    if committed_contamination:
        return None, fail(
            "C1 failed: experiment scaffolding was committed: "
            + ", ".join(committed_contamination)
        )
    count_proc = run_git(checkout, ["rev-list", "--count", f"{base_hash}..HEAD"], capture=True)
    if count_proc.returncode != 0:
        return None, fail(f"could not compare base {base_hash} to HEAD")
    commit_count = int(count_proc.stdout.strip())
    if commit_count != 1:
        return None, fail(
            f"C1 failed: expected exactly one Slice 1 commit after base, got {commit_count}"
        )

    diff_files = changed_files(checkout)
    test_files = [path for path in diff_files if is_test_file(path)]
    if not test_files:
        return None, fail("P1 failed / void 1b risk: no uncommitted Slice 2 test file diff")
    disallowed = [path for path in diff_files if not allowed_checkpoint_file(path, arm)]
    if disallowed:
        return None, fail(
            "P3/A5 failed / void 1a risk: implementation or unexpected files touched: "
            + ", ".join(disallowed)
        )
    return {
        "base": base_hash,
        "head": head,
        "diff_files": diff_files,
        "test_files": test_files,
        "test_count": len(test_files),
    }, 0


def command_doctor(args: argparse.Namespace) -> int:
    failures = 0
    if (ascs_root() / "scripts/ascs.py").exists():
        print("PASS scripts/ascs.py exists")
    else:
        print("FAIL scripts/ascs.py is missing")
        failures += 1
    target_repo = Path(args.target_repo).expanduser().resolve()
    if ensure_git_worktree(target_repo, "target repo"):
        failures += 1
    else:
        print(f"PASS target repo exists and is a git work tree: {target_repo}")
    root = sandbox_root(args.sandbox_root)
    for arm in ARMS.values():
        path = checkout_path(arm, root)
        if path.exists():
            print(f"FAIL checkout path already exists: {path}")
            failures += 1
        else:
            print(f"PASS checkout path is available: {path}")
    warning = maybe_project_state_warning(root)
    print(f"WARN Claude Code project-state check: {warning}")
    return 1 if failures else 0


def command_prepare_arm(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    source_repo = Path(args.target_repo).expanduser().resolve()
    if ensure_git_worktree(source_repo, "target repo"):
        return 1
    if ensure_clean(source_repo):
        return 1
    base_hash, status = resolve_commit(source_repo, args.base)
    if status:
        return status
    assert base_hash is not None

    root = sandbox_root(args.sandbox_root)
    checkout = checkout_path(arm, root)
    if checkout.exists():
        return fail(f"checkout already exists: {checkout}")
    try:
        checkout.parent.mkdir(parents=True, exist_ok=False)
    except OSError:
        return fail_prepare(arm, checkout, base_hash, "create-sandbox-directory")
    proc = run_cmd(["git", "clone", "--no-checkout", str(source_repo), str(checkout)], ascs_root())
    if not require_success(proc, f"git clone --no-checkout {source_repo} {checkout}"):
        return fail_prepare(arm, checkout, base_hash, "clone")
    if disable_push_remotes(checkout):
        return fail_prepare(arm, checkout, base_hash, "disable-push")
    proc = run_git(checkout, ["switch", "-c", arm.branch, base_hash])
    if not require_success(proc, f"git switch -c {arm.branch} {base_hash}"):
        return fail_prepare(arm, checkout, base_hash, "switch-branch")

    try:
        if arm.condition == "baseline":
            if verify_baseline_setup(checkout):
                return fail_prepare(arm, checkout, base_hash, "verify-baseline")
        else:
            if setup_treated(checkout):
                return fail_prepare(arm, checkout, base_hash, "setup-treated")
    except (OSError, UnicodeError, shutil.Error):
        return fail_prepare(arm, checkout, base_hash, "configure-arm")

    if record_event(arm, "isolation-setup", isolation_setup_note(arm, checkout, base_hash)):
        return fail_prepare(arm, checkout, base_hash, "record-isolation-setup")
    arm_start_note = (
        f"arm_start; condition: {arm.condition}; task: {arm.task}; "
        f"branch: {arm.branch}; base commit: {base_hash}; checkout_id: {arm.name}"
    )
    if record_event(arm, "arm_start", arm_start_note):
        return fail_prepare(arm, checkout, base_hash, "record-arm-start")
    print(build_prompt(arm, "first"), end="")
    return 0


def command_check_checkpoint(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    signature, status = checkpoint_signature(arm, Path(args.checkout).expanduser().resolve())
    if status:
        return status
    assert signature is not None
    print("PASS checkpoint mechanical shape")
    print(json.dumps(signature, indent=2, sort_keys=True))
    return 0


def command_record_interruption(args: argparse.Namespace) -> int:
    if not args.slice1_suite_green or not args.checkpoint_suite_red_only_slice2:
        return fail("missing required suite attestation flags; do not record interruption_reached")
    if args.failing_count <= 0:
        return fail("--failing-count must be positive")
    arm = arm_from_name(args.arm)
    signature, status = checkpoint_signature(arm, Path(args.checkout).expanduser().resolve())
    if status:
        return status
    assert signature is not None
    note = (
        "interruption boundary reached; "
        f"slice1_suite_green=true; checkpoint_suite_red_only_slice2=true; "
        f"failing_count={args.failing_count}; signature="
        + json.dumps(signature, sort_keys=True)
    )
    return record_event(arm, "interruption_reached", note)


def command_verify_pair_checkpoint(args: argparse.Namespace) -> int:
    left_name, right_name = PAIR_ARMS[args.pair]
    arms = [arm_from_name(left_name), arm_from_name(right_name)]
    for arm in arms:
        if not has_event(arm, "interruption_reached"):
            return fail(f"{arm.name} has no interruption_reached event")
    note = f"pair-checkpoint-audit; pair={args.pair}; scope_differs={args.scope_differs}"
    if args.scope_differs:
        note += "; operator judged scope materially different; pair should be void condition 3"
    return record_pair_event(
        args.pair,
        "pair-checkpoint-audit",
        note,
        f"exp004-pair-{args.pair}-checkpoint-audit",
    )


def command_print_prompt(args: argparse.Namespace) -> int:
    print(build_prompt(arm_from_name(args.arm), args.phase), end="")
    return 0


def command_record_resume_start(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    if not has_event(arm, "interruption_reached"):
        return fail(f"{arm.name} has no interruption_reached event")
    if not pair_event_committed(arm.pair, "pair-checkpoint-audit"):
        return fail(f"pair {arm.pair} has no committed pair-checkpoint-audit event")
    if has_event(arm, "first-progress-edit"):
        return fail(f"{arm.name} already has first-progress-edit")
    if has_event(arm, "resume-start") and last_event_name(arm) != "resume-attempt-aborted":
        return fail("duplicate resume-start is allowed only directly after resume-attempt-aborted")
    note = "resume prompt send begins immediately after this event; prompt must be pre-copied"
    status = record_event(arm, "resume-start", note)
    if status:
        return status
    print("PASS resume-start recorded. Send the pre-copied resume prompt now.")
    return 0


def command_record_resume_attempt_aborted(args: argparse.Namespace) -> int:
    if not args.no_recovery_work_started:
        return fail("--no-recovery-work-started is mandatory; otherwise the pair is void")
    arm = arm_from_name(args.arm)
    if not has_event(arm, "resume-start"):
        return fail(f"{arm.name} has no resume-start event to abort")
    return record_event(arm, "resume-attempt-aborted", f"reason: {args.reason}")


def command_record_first_progress_edit(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    if not has_event(arm, "resume-start"):
        return fail(f"{arm.name} has no resume-start event")
    if has_event(arm, "first-progress-edit"):
        return fail(f"{arm.name} already has first-progress-edit")
    status = record_event(arm, "first-progress-edit", "operator observed first durable target edit")
    if status:
        return status
    print("Reminder: this is valid only if recorded before the next operator message and before a second durable target edit.")
    return 0


def command_finish_arm(args: argparse.Namespace) -> int:
    import ascs

    arm = arm_from_name(args.arm)
    experiment_dir = experiment_path(arm)
    experiment_json = experiment_dir / "experiment.json"
    if not experiment_json.exists():
        return fail(f"{experiment_json} does not exist")

    derived, detail = ascs.derive_resume_time(events_path(arm))
    if derived is None:
        return fail(
            f"cannot determine resume_time_seconds: {detail}. "
            f"Record `{ascs.RESUME_START_EVENT}` and `{ascs.FIRST_PROGRESS_EVENT}` before finishing."
        )

    missed_state_files = ascs.parse_count_or_na(args.missed_state_files)
    metrics = {
        "resume_time_seconds": derived,
        "missed_checkpoint_items": args.missed_checkpoint_items,
        "missed_state_files": missed_state_files,
        "human_corrections": args.human_corrections,
        "recovery_quality": args.recovery_quality,
    }
    data = ascs.read_json(experiment_json)
    data["metrics"] = metrics
    data["gate_profile"] = ascs.GATE_PROFILE_EXPERIMENT_004
    data["finished_at"] = ascs.now_iso()
    data["score"] = ascs.calculate_score(
        metrics,
        gate_profile=ascs.GATE_PROFILE_EXPERIMENT_004,
    )
    ascs.write_json(experiment_json, data)
    print(f"PASS resume_time_seconds={derived} derived from events ({detail})")
    print(f"PASS finished {experiment_dir} without rewriting report.md")
    return 0


def metrics_for_arm(arm: Arm) -> dict[str, object]:
    path = experiment_path(arm) / "experiment.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{path} has no metrics object")
    return metrics


def verdict_tuple(metrics: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(metrics["missed_checkpoint_items"]),
        int(metrics["human_corrections"]),
        -int(metrics["recovery_quality"]),
    )


def command_pair_verdict(args: argparse.Namespace) -> int:
    left_name, right_name = PAIR_ARMS[args.pair]
    left = arm_from_name(left_name)
    right = arm_from_name(right_name)
    if pair_event_committed(args.pair, "void-pair"):
        return fail(f"pair {args.pair} has a committed void-pair event; no verdict arithmetic allowed")
    if pair_event_pending(args.pair, "void-pair"):
        return fail(f"pair {args.pair} has a pending void-pair transaction; recover it first")
    left_metrics = metrics_for_arm(left)
    right_metrics = metrics_for_arm(right)
    left_tuple = verdict_tuple(left_metrics)
    right_tuple = verdict_tuple(right_metrics)
    if left_tuple < right_tuple:
        winner = left.name
    elif right_tuple < left_tuple:
        winner = right.name
    else:
        winner = "tie"
    note = (
        f"pair-verdict; pair={args.pair}; winner={winner}; "
        f"{left.name}={left_tuple}; {right.name}={right_tuple}; "
        "resume_time_seconds=reported only"
    )
    status = record_pair_event(
        args.pair,
        "pair-verdict",
        note,
        f"exp004-pair-{args.pair}-verdict",
    )
    if status == 0:
        print(note)
    return status


def pair_winner(pair: str) -> str:
    left = arm_from_name(PAIR_ARMS[pair][0])
    right = arm_from_name(PAIR_ARMS[pair][1])
    left_tuple = verdict_tuple(metrics_for_arm(left))
    right_tuple = verdict_tuple(metrics_for_arm(right))
    if left_tuple < right_tuple:
        return left.condition
    if right_tuple < left_tuple:
        return right.condition
    return "tie"


def command_claim_check(args: argparse.Namespace) -> int:
    for pair in PAIR_ARMS:
        if pair_event_pending(pair, "void-pair") or pair_event_pending(pair, "pair-verdict"):
            return fail(f"pair {pair} has a pending pair transaction; recover it before claims")
        if pair_event_committed(pair, "void-pair"):
            return fail("a committed void-pair event exists; Experiment 004 closes without Layer 3 claim")
        if not pair_event_committed(pair, "pair-verdict"):
            return fail(f"pair {pair} has no committed pair-verdict transaction")
    winners = (pair_winner("1"), pair_winner("2"))
    print(f"Pair winners: {winners[0]}, {winners[1]}")
    if winners == ("treated", "treated"):
        print("Permitted statement: limited positive signal in 2/2 pre-registered pairs; n=2 consistency evidence, not proof of effect.")
    elif "baseline" in winners:
        print("Permitted statement: no positive ASCS recovery claim.")
    else:
        print("Permitted statement: below claim threshold; direction reported descriptively only.")
    print("Forbidden: model superiority, full-stack effect, benchmark, proof, speed, or production-readiness claims.")
    return 0


def command_record_void_pair(args: argparse.Namespace) -> int:
    return record_pair_event(
        args.pair,
        "void-pair",
        f"condition={args.condition}; note={args.note}",
        f"exp004-pair-{args.pair}-void",
    )


def command_status(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    path = events_path(arm)
    if not path.exists():
        return fail(f"events file does not exist: {path}")
    for event in load_events(arm):
        print(f"{event.get('timestamp', '<missing>')}\t{event.get('event', '<missing>')}")
    return 0


def add_arm_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("arm", choices=sorted(ARMS))


def add_pair_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pair", choices=sorted(PAIR_ARMS))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Experiment 004 operator helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--target-repo", required=True)
    doctor_parser.add_argument("--sandbox-root", default=DEFAULT_SANDBOX_ROOT)
    doctor_parser.set_defaults(func=command_doctor)

    prepare_parser = subparsers.add_parser("prepare-arm")
    add_arm_argument(prepare_parser)
    prepare_parser.add_argument("--target-repo", required=True)
    prepare_parser.add_argument("--sandbox-root", default=DEFAULT_SANDBOX_ROOT)
    prepare_parser.add_argument("--base", required=True)
    prepare_parser.set_defaults(func=command_prepare_arm)

    check_parser = subparsers.add_parser("check-checkpoint")
    add_arm_argument(check_parser)
    check_parser.add_argument("--checkout", required=True)
    check_parser.set_defaults(func=command_check_checkpoint)

    interruption_parser = subparsers.add_parser("record-interruption")
    add_arm_argument(interruption_parser)
    interruption_parser.add_argument("--checkout", required=True)
    interruption_parser.add_argument("--slice1-suite-green", action="store_true")
    interruption_parser.add_argument("--checkpoint-suite-red-only-slice2", action="store_true")
    interruption_parser.add_argument("--failing-count", required=True, type=int)
    interruption_parser.set_defaults(func=command_record_interruption)

    pair_audit_parser = subparsers.add_parser("verify-pair-checkpoint")
    add_pair_argument(pair_audit_parser)
    pair_audit_parser.add_argument("--scope-differs", action="store_true")
    pair_audit_parser.set_defaults(func=command_verify_pair_checkpoint)

    prompt_parser = subparsers.add_parser("print-prompt")
    add_arm_argument(prompt_parser)
    prompt_parser.add_argument("--phase", required=True, choices=("first", "resume"))
    prompt_parser.set_defaults(func=command_print_prompt)

    resume_parser = subparsers.add_parser("record-resume-start")
    add_arm_argument(resume_parser)
    resume_parser.set_defaults(func=command_record_resume_start)

    abort_parser = subparsers.add_parser("record-resume-attempt-aborted")
    add_arm_argument(abort_parser)
    abort_parser.add_argument("--reason", required=True)
    abort_parser.add_argument("--no-recovery-work-started", action="store_true")
    abort_parser.set_defaults(func=command_record_resume_attempt_aborted)

    first_edit_parser = subparsers.add_parser("record-first-progress-edit")
    add_arm_argument(first_edit_parser)
    first_edit_parser.set_defaults(func=command_record_first_progress_edit)

    finish_parser = subparsers.add_parser("finish-arm")
    add_arm_argument(finish_parser)
    finish_parser.add_argument("--missed-checkpoint-items", required=True, type=int)
    finish_parser.add_argument("--human-corrections", required=True, type=int)
    finish_parser.add_argument("--recovery-quality", required=True, type=int, choices=(0, 1, 2, 3, 4))
    finish_parser.add_argument("--missed-state-files", default="n/a")
    finish_parser.set_defaults(func=command_finish_arm)

    pair_verdict_parser = subparsers.add_parser("pair-verdict")
    add_pair_argument(pair_verdict_parser)
    pair_verdict_parser.set_defaults(func=command_pair_verdict)

    claim_parser = subparsers.add_parser("claim-check")
    claim_parser.set_defaults(func=command_claim_check)

    void_parser = subparsers.add_parser("record-void-pair")
    add_pair_argument(void_parser)
    void_parser.add_argument("--condition", required=True, choices=VOID_CONDITIONS)
    void_parser.add_argument("--note", required=True)
    void_parser.set_defaults(func=command_record_void_pair)

    status_parser = subparsers.add_parser("status")
    add_arm_argument(status_parser)
    status_parser.set_defaults(func=command_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
