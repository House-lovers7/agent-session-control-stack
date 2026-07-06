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
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TARGET_REPO = "/Users/tg/projects/app_development/supabase-rls-guard"
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
        experiment_dir="experiments/2026-07-06-claude-code-handoff-004-p1-baseline",
        task="T-A rename tracking + extension_in_public",
        condition="baseline",
        order=1,
        pair="1",
        branch="exp-004-p1-baseline",
    ),
    "004-p1-treated": Arm(
        name="004-p1-treated",
        experiment_dir="experiments/2026-07-06-claude-code-handoff-004-p1-treated",
        task="T-A rename tracking + extension_in_public",
        condition="treated",
        order=2,
        pair="1",
        branch="exp-004-p1-treated",
    ),
    "004-p2-treated": Arm(
        name="004-p2-treated",
        experiment_dir="experiments/2026-07-06-claude-code-handoff-004-p2-treated",
        task="T-B CTAS modeling + Splinter 0004 no_primary_key",
        condition="treated",
        order=3,
        pair="2",
        branch="exp-004-p2-treated",
    ),
    "004-p2-baseline": Arm(
        name="004-p2-baseline",
        experiment_dir="experiments/2026-07-06-claude-code-handoff-004-p2-baseline",
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
    proc = run_git(repo, ["status", "--porcelain"], capture=True)
    if proc.returncode != 0:
        return fail(f"could not inspect working tree: {repo}")
    if proc.stdout.strip():
        print(proc.stdout, end="", file=sys.stderr)
        return fail(f"working tree is not clean: {repo}")
    return 0


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


def record_event(arm: Arm, event_name: str, note: str) -> int:
    return run_ascs(
        [
            "record",
            "--experiment",
            arm.experiment_dir,
            "--event",
            event_name,
            "--note",
            note,
        ]
    )


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def global_claude_checksum() -> str:
    return sha256_file(Path("~/.claude/CLAUDE.md").expanduser())


def maybe_project_state_warning(checkout: Path) -> str:
    projects_dir = Path("~/.claude/projects").expanduser()
    if not projects_dir.exists():
        return "claude project state dir missing"
    encoded = str(checkout).replace("/", "-")
    matches = [path.name for path in projects_dir.iterdir() if encoded in path.name]
    if matches:
        return "exact project state match detected: " + ", ".join(sorted(matches))
    return "no exact project state match detected"


def write_neutral_state_file(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {title}\n\n"
        "<!-- Neutral Experiment 004 scaffold. Fill during the measured session. -->\n",
        encoding="utf-8",
    )


def setup_treated(checkout: Path) -> int:
    claude_path = checkout / "CLAUDE.md"
    if not claude_path.exists():
        claude_path.write_text("# CLAUDE.md\n", encoding="utf-8")
    content = claude_path.read_text(encoding="utf-8")
    if MARKER_BEGIN in content or MARKER_END in content:
        return fail("target CLAUDE.md already contains an exp-004 ASCS marker")
    session_dir = checkout / ".agent-session"
    if session_dir.exists():
        return fail("target repo already contains .agent-session/")
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

    (session_dir / "state").mkdir(parents=True)
    shutil.copyfile(ascs_root() / "templates/session-handoff.md", session_dir / "handoff.md")
    shutil.copyfile(
        ascs_root() / "templates/state-file.md",
        session_dir / "state" / "checkpoint.md",
    )
    shutil.copyfile(
        ascs_root() / "templates/decision-log.md",
        session_dir / "state" / "decision-log.md",
    )
    write_neutral_state_file(session_dir / "state" / "current-plan.md", "Current Plan")
    write_neutral_state_file(session_dir / "state" / "failed-attempts.md", "Failed Attempts")
    write_neutral_state_file(session_dir / "state" / "recovery-notes.md", "Recovery Notes")
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
    return 0


def build_prompt(arm: Arm, phase: str) -> str:
    task_text = TASK_TEXT[arm.pair]
    if phase == "first":
        if arm.condition == "baseline":
            condition = """Condition:
- Use standard Claude Code operation.
- Do not create or use `.agent-session/`.
- Use the target repo's normal instructions (`CLAUDE.md`, README) as usual.
- Do not push, release, create issues, create PRs, or use other AI help."""
        else:
            condition = """Condition:
- Read root `CLAUDE.md`, `.agent-session/handoff.md`, and `.agent-session/state/`
  before making task edits.
- Follow the ASCS handoff/state protocol in the marker block.
- Do not push, release, create issues, create PRs, or use other AI help."""
        return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

Experiment 004 {arm.condition} arm の first session です。
repo: supabase-rls-guard
branch: {arm.branch}

{condition}

Task:
{task_text}

Work order:
- Complete Slice 1 first.
- Commit Slice 1 only after its tests and the full suite are green.
- Then write Slice 2 tests first.
- Run the suite and confirm only the new Slice 2 tests fail.
- Report and wait before editing any Slice 2 implementation file.
"""

    if arm.condition == "baseline":
        constraint = """Constraints:
- Continue with standard Claude Code operation.
- Do not use `.agent-session/`.
- Do not use any transcript, summary, or operator supplement from the prior session.
- Do not push, release, create issues, create PRs, or use other AI help."""
    else:
        constraint = """Constraints:
- First read root `CLAUDE.md`, `.agent-session/handoff.md`, and `.agent-session/state/`.
- Summarize what you verified from those files before making task edits.
- Follow the ASCS handoff/state protocol.
- Do not use any transcript, summary, or operator supplement from the prior session.
- Do not push, release, create issues, create PRs, or use other AI help."""
    return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

前回の fresh session は checkpoint で終了しました。同じタスクを完了してください。

Task:
{task_text}

{constraint}
"""


def changed_files(checkout: Path) -> list[str]:
    proc = run_git(checkout, ["status", "--porcelain", "-uall"], capture=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "git status failed")
    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip())
    return files


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
    checkout.parent.mkdir(parents=True, exist_ok=False)
    proc = run_cmd(["git", "clone", "--no-checkout", str(source_repo), str(checkout)], ascs_root())
    if not require_success(proc, f"git clone --no-checkout {source_repo} {checkout}"):
        return 1
    proc = run_git(checkout, ["switch", "-c", arm.branch, base_hash])
    if not require_success(proc, f"git switch -c {arm.branch} {base_hash}"):
        return 1

    if arm.condition == "baseline":
        if verify_baseline_setup(checkout):
            return 1
    else:
        if setup_treated(checkout):
            return 1

    isolation_note = (
        f"isolation-setup; checkout: {checkout}; base commit: {base_hash}; "
        f"global CLAUDE.md sha256: {global_claude_checksum()}; "
        f"project-state: {maybe_project_state_warning(checkout)}"
    )
    if record_event(arm, "isolation-setup", isolation_note):
        return 1
    arm_start_note = (
        f"arm_start; condition: {arm.condition}; task: {arm.task}; "
        f"branch: {arm.branch}; base commit: {base_hash}; checkout: {checkout}"
    )
    if record_event(arm, "arm_start", arm_start_note):
        return 1
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
    for arm in arms:
        if record_event(arm, "pair-checkpoint-audit", note):
            return 1
    print("PASS pair checkpoint audit recorded")
    return 0


def command_print_prompt(args: argparse.Namespace) -> int:
    print(build_prompt(arm_from_name(args.arm), args.phase), end="")
    return 0


def command_record_resume_start(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    if not has_event(arm, "interruption_reached"):
        return fail(f"{arm.name} has no interruption_reached event")
    if not has_event(arm, "pair-checkpoint-audit"):
        return fail(f"{arm.name} has no pair-checkpoint-audit event")
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
    arm = arm_from_name(args.arm)
    missed_state_files = args.missed_state_files
    finish_args = [
        "finish",
        "--experiment",
        arm.experiment_dir,
        "--gate-profile",
        "experiment-004",
        "--missed-checkpoint-items",
        str(args.missed_checkpoint_items),
        "--missed-state-files",
        missed_state_files,
        "--human-corrections",
        str(args.human_corrections),
        "--recovery-quality",
        str(args.recovery_quality),
    ]
    return run_ascs(finish_args)


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
    for arm in (left, right):
        if has_event(arm, "void-pair"):
            return fail(f"{arm.name} has a void-pair event; no verdict arithmetic allowed")
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
    for arm in (left, right):
        if record_event(arm, "pair-verdict", note):
            return 1
    print(note)
    return 0


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
    for arm in ARMS.values():
        if has_event(arm, "void-pair"):
            return fail("a void-pair event exists; Experiment 004 closes without Layer 3 claim")
    for pair, names in PAIR_ARMS.items():
        if not all(has_event(arm_from_name(name), "pair-verdict") for name in names):
            return fail(f"pair {pair} has no complete pair-verdict events")
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
    for name in PAIR_ARMS[args.pair]:
        arm = arm_from_name(name)
        if record_event(arm, "void-pair", f"condition={args.condition}; note={args.note}"):
            return 1
    print(f"PASS void-pair recorded for pair {args.pair}")
    return 0


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
    doctor_parser.add_argument("--target-repo", default=DEFAULT_TARGET_REPO)
    doctor_parser.add_argument("--sandbox-root", default=DEFAULT_SANDBOX_ROOT)
    doctor_parser.set_defaults(func=command_doctor)

    prepare_parser = subparsers.add_parser("prepare-arm")
    add_arm_argument(prepare_parser)
    prepare_parser.add_argument("--target-repo", default=DEFAULT_TARGET_REPO)
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
