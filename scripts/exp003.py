#!/usr/bin/env python3
"""Operator helper for Experiment 003.

This script prepares target-repo branches and records manual Experiment 003
events through scripts/ascs.py. It never starts Codex, Claude, pushes, opens
PRs, or writes under experiments/ directly.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MARKER_BEGIN = "<!-- BEGIN ASCS EXPERIMENT SCAFFOLDING (exp-003) — do not commit -->"
MARKER_END = "<!-- END ASCS EXPERIMENT SCAFFOLDING (exp-003) -->"
AMENDMENT_NOTE = (
    "Amendment before any session: resume prompts instruct the worker to pause "
    "immediately before the first durable edit and wait for the operator to "
    "record first-progress-edit. Symmetric in both arms; adds operator response "
    "latency to the measured interval."
)
REQUIRED_STATE_FILES = [
    "handoff.md",
    "state/current-plan.md",
    "state/decision-log.md",
    "state/failed-attempts.md",
    "state/checkpoint.md",
    "state/recovery-notes.md",
]


@dataclass(frozen=True)
class Arm:
    name: str
    experiment_dir: str
    task: str
    condition: str
    order: int
    pair: str
    branch: str
    task_source: str
    # 1 = single pre-regex-parity window (original 003 pairs); 2 = the
    # re-registered two-checkpoint boundary (design doc, Re-registration).
    checkpoints: int = 1


ARMS = {
    "003-p1-baseline": Arm(
        name="003-p1-baseline",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p1-baseline",
        task="T1 RLS012 materialized_view_in_api",
        condition="baseline",
        order=1,
        pair="1",
        branch="exp-003-p1-baseline",
        task_source="003-p1-baseline",
    ),
    "003-p1-treated": Arm(
        name="003-p1-treated",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p1-treated",
        task="T1 RLS012 materialized_view_in_api",
        condition="treated",
        order=2,
        pair="1",
        branch="exp-003-p1-treated",
        task_source="003-p1-baseline",
    ),
    "003-p2-treated": Arm(
        name="003-p2-treated",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p2-treated",
        task="T2 RLS014 foreign_table_in_api",
        condition="treated",
        order=3,
        pair="2",
        branch="exp-003-p2-treated",
        task_source="003-p2-treated",
    ),
    "003-p2-baseline": Arm(
        name="003-p2-baseline",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p2-baseline",
        task="T2 RLS014 foreign_table_in_api",
        condition="baseline",
        order=4,
        pair="2",
        branch="exp-003-p2-baseline",
        task_source="003-p2-treated",
    ),
    "003-p1r-baseline": Arm(
        name="003-p1r-baseline",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p1r-baseline",
        task="T1' partial REVOKE semantics + RLS014 foreign_table_in_api",
        condition="baseline",
        order=1,
        pair="1r",
        branch="exp-003-p1r-baseline",
        task_source="003-p1r-baseline",
        checkpoints=2,
    ),
    "003-p1r-treated": Arm(
        name="003-p1r-treated",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p1r-treated",
        task="T1' partial REVOKE semantics + RLS014 foreign_table_in_api",
        condition="treated",
        order=2,
        pair="1r",
        branch="exp-003-p1r-treated",
        task_source="003-p1r-baseline",
        checkpoints=2,
    ),
    "003-p2r-treated": Arm(
        name="003-p2r-treated",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p2r-treated",
        task="T2' ALTER POLICY RENAME identity tracking + extension_in_public",
        condition="treated",
        order=3,
        pair="2r",
        branch="exp-003-p2r-treated",
        task_source="003-p2r-treated",
        checkpoints=2,
    ),
    "003-p2r-baseline": Arm(
        name="003-p2r-baseline",
        experiment_dir="experiments/2026-07-06-codex-handoff-003-p2r-baseline",
        task="T2' ALTER POLICY RENAME identity tracking + extension_in_public",
        condition="baseline",
        order=4,
        pair="2r",
        branch="exp-003-p2r-baseline",
        task_source="003-p2r-treated",
        checkpoints=2,
    ),
}

PAIR_FIRST_ARM = {
    "1": "003-p1-baseline",
    "2": "003-p2-treated",
    "1r": "003-p1r-baseline",
    "2r": "003-p2r-treated",
}


def ascs_root() -> Path:
    return Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fail(message: str) -> int:
    print(f"FAIL {message}", file=sys.stderr)
    return 1


def arm_from_name(name: str) -> Arm:
    return ARMS[name]


def experiment_path(arm: Arm) -> Path:
    return ascs_root() / arm.experiment_dir


def events_path(arm: Arm) -> Path:
    return experiment_path(arm) / "events.jsonl"


def run_cmd(cmd: list[str], cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )


def run_git(target_repo: Path, args: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run_cmd(["git"] + args, target_repo, capture=capture)


def require_success(proc: subprocess.CompletedProcess[str], command_text: str) -> bool:
    if proc.returncode == 0:
        return True
    if proc.stdout:
        print(proc.stdout, end="", file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    print(f"FAIL command failed: {command_text}", file=sys.stderr)
    return False


def ensure_target_repo(path_text: str) -> tuple[Path | None, int]:
    target_repo = Path(path_text).expanduser().resolve()
    if not target_repo.exists():
        return None, fail(f"target repo does not exist: {target_repo}")
    proc = run_git(target_repo, ["rev-parse", "--is-inside-work-tree"], capture=True)
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return None, fail(f"target repo is not a git work tree: {target_repo}")
    return target_repo, 0


def ensure_clean(target_repo: Path) -> int:
    proc = run_git(
        target_repo,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture=True,
    )
    if proc.returncode != 0:
        return fail("could not inspect target repo working tree")
    entries = parse_porcelain_z(proc.stdout)
    if entries:
        for status, path in entries:
            print(f"{status} {path}", file=sys.stderr)
        return fail("target repo working tree is not clean")
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


def resolve_commit(target_repo: Path, commit: str) -> tuple[str | None, int]:
    proc = run_git(target_repo, ["rev-parse", "--verify", f"{commit}^{{commit}}"], capture=True)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        return None, fail(f"base commit does not exist: {commit}")
    return proc.stdout.strip(), 0


def branch_exists(target_repo: Path, branch: str) -> bool:
    proc = run_git(target_repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    return proc.returncode == 0


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


def arm_start_base(arm: Arm) -> str | None:
    for event in load_events(arm):
        if event.get("event") != "arm_start":
            continue
        note = str(event.get("note", ""))
        match = re.search(r"\bbase commit: ([0-9a-f]{40})\b", note)
        if match:
            return match.group(1)
    return None


def verify_pair_base(arm: Arm, base_hash: str) -> int:
    first_arm_name = PAIR_FIRST_ARM[arm.pair]
    if arm.name == first_arm_name:
        return 0
    first_arm = arm_from_name(first_arm_name)
    recorded_base = arm_start_base(first_arm)
    if recorded_base is None:
        return fail(
            f"{arm.name} is the second arm in pair {arm.pair}, but "
            f"{first_arm.name} has no arm_start note with a base commit"
        )
    if recorded_base != base_hash:
        return fail(
            f"pair {arm.pair} base mismatch: {arm.name} base {base_hash} "
            f"!= {first_arm.name} recorded base {recorded_base}"
        )
    return 0


def report_section(report: str, heading: str, next_heading: str | None) -> str | None:
    start_marker = f"## {heading}"
    start = report.find(start_marker)
    if start == -1:
        return None
    content_start = report.find("\n", start)
    if content_start == -1:
        return None
    content_start += 1
    if next_heading:
        end = report.find(f"\n## {next_heading}", content_start)
        if end == -1:
            return None
    else:
        end = len(report)
    return report[content_start:end].strip() or None


def task_text_for_prompt(arm: Arm) -> str:
    source_arm = arm_from_name(arm.task_source)
    report_path = experiment_path(source_arm) / "report.md"
    report = report_path.read_text(encoding="utf-8")
    task_summary = report_section(report, "Task Summary", "Events")
    if task_summary is None:
        raise ValueError(f"{report_path} has no Task Summary section")
    task_start = task_summary.find("**Task")
    condition_start = task_summary.find("\n**Condition", task_start)
    if task_start == -1 or condition_start == -1:
        raise ValueError(f"{report_path} Task Summary does not contain a full task and condition")
    return task_summary[task_start:condition_start].strip()


def first_session_flow(arm: Arm) -> str:
    if arm.checkpoints == 2:
        return """進め方:
- Part A から着手し、libpg backend で新しいテストが通る状態まで進める
- Part A が libpg backend で green になったら、Part B に着手する前に、
  いったん停止して operator に確認を求める (checkpoint 1)
- operator の指示後に Part B へ進み、Part B のルールが libpg backend の
  テストで発火したら、regex parity の完了・docs/README 更新・最終
  all-green run の前に再度停止して operator に確認を求める (checkpoint 2)
- operator が中断を指示したら直ちに停止し、完了した内容 / 未完了の内容 /
  作業ツリー状態を報告する"""
    return """進め方:
- libpg backend での実装とテストから着手する
- regex backend の parity、docs/README 更新、最終 all-green run へ進む前に、
  いったん停止して operator に確認を求める
- operator が中断を指示したら直ちに停止し、完了した内容 / 未完了の内容 /
  作業ツリー状態を報告する"""


def build_prompt(arm: Arm, phase: str) -> str:
    task_text = task_text_for_prompt(arm)
    if phase == "first":
        if arm.condition == "baseline":
            conditions = """条件:
- ASCS handoff/state protocol は使わない。.agent-session/ は作らない・使わない
- repo 自身の AGENTS.md (contributor guide) は通常どおり参照してよい
- push / release / issue / PR はしない
- 他のAIのレビュー・支援は使わない"""
        else:
            conditions = """条件:
- root AGENTS.md を読み、記載の handoff/state protocol に従う
- 作業前に .agent-session/handoff.md と .agent-session/state/ 配下を読む
- 決定・却下した案・失敗した試行は、発生したその時点で decision-log.md /
  failed-attempts.md に記録する
- 停止・中断の前に handoff.md を更新する
- push / release / issue / PR はしない
- 他のAIのレビュー・支援は使わない"""
        return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

Experiment 003 {arm.condition} arm の作業セッションです。
repo: supabase-rls-guard / branch: {arm.branch}

{conditions}

タスク:
{task_text}

{first_session_flow(arm)}
"""

    if arm.condition == "baseline":
        constraints = """制約:
- ASCS handoff/state protocol は使わない。.agent-session/ は使わない
- repo 自身の AGENTS.md は通常どおり参照してよい
- push / release / issue / PR はしない
- 他のAIのレビュー・支援は使わない"""
    else:
        constraints = """制約:
- 最初に root AGENTS.md → .agent-session/handoff.md →
  .agent-session/state/ 配下 (current-plan.md / decision-log.md /
  failed-attempts.md、必要なら checkpoint.md / recovery-notes.md) を読み、
  読んだ内容を短く要約してから作業する
- root AGENTS.md に記載の handoff/state protocol に従う
- repo 自身の AGENTS.md は通常どおり参照してよい
- push / release / issue / PR はしない
- 他のAIのレビュー・支援は使わない"""
    return f"""日本語で回答してください。
コード、ファイル名、コマンド、識別子は英語のままにしてください。

前回のセッションは中断されました。同じタスクの続きを完了してください。

タスク:
{task_text}

{constraints}

測定手続き (実験の記録用):
- 最終成果物に残る最初のファイル編集を行う直前に、いったん停止して
  operator に「first-progress-edit を record してください」と伝え、
  operator の返信を待ってから編集を開始する。それ以降の停止は不要
"""


def verify_baseline_setup(target_repo: Path) -> int:
    agents_path = target_repo / "AGENTS.md"
    if not agents_path.exists():
        return fail("baseline requires the target repo's AGENTS.md to exist")
    content = agents_path.read_text(encoding="utf-8")
    if MARKER_BEGIN in content or MARKER_END in content:
        return fail("baseline target AGENTS.md contains an ASCS experiment marker")
    if (target_repo / ".agent-session").exists():
        return fail("baseline target repo contains .agent-session/")
    return 0


def verify_treated_setup(target_repo: Path) -> int:
    agents_path = target_repo / "AGENTS.md"
    if not agents_path.exists():
        return fail("treated setup requires the target repo's AGENTS.md to exist")
    content = agents_path.read_text(encoding="utf-8")
    if content.count(MARKER_BEGIN) != 1 or content.count(MARKER_END) != 1:
        return fail("treated target AGENTS.md must contain exactly one ASCS marker block")
    session_dir = target_repo / ".agent-session"
    missing = [path for path in REQUIRED_STATE_FILES if not (session_dir / path).exists()]
    if missing:
        return fail("treated .agent-session/ is missing files: " + ", ".join(missing))
    return 0


def setup_treated(target_repo: Path) -> int:
    root = ascs_root()
    agents_path = target_repo / "AGENTS.md"
    if not agents_path.exists():
        return fail("treated setup requires the target repo's AGENTS.md to exist")
    content = agents_path.read_text(encoding="utf-8")
    if MARKER_BEGIN in content or MARKER_END in content:
        return fail("target AGENTS.md already contains an ASCS experiment marker")
    session_dir = target_repo / ".agent-session"
    if session_dir.exists():
        return fail("target repo already contains .agent-session/")
    scaffold = (root / "examples/codex/AGENTS.md").read_text(encoding="utf-8")
    source_session = root / "examples/codex/.agent-session"
    missing_source = [path for path in REQUIRED_STATE_FILES if not (source_session / path).exists()]
    if missing_source:
        return fail("ASCS source .agent-session/ is missing files: " + ", ".join(missing_source))

    with agents_path.open("a", encoding="utf-8") as f:
        if content and not content.endswith("\n"):
            f.write("\n")
        f.write("\n")
        f.write(MARKER_BEGIN)
        f.write("\n")
        f.write(scaffold.rstrip())
        f.write("\n")
        f.write(MARKER_END)
        f.write("\n")
    shutil.copytree(str(source_session), str(session_dir))
    return verify_treated_setup(target_repo)


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


def command_doctor(args: argparse.Namespace) -> int:
    root = ascs_root()
    failures = 0
    ascs_path = root / "scripts/ascs.py"
    if ascs_path.exists():
        print("PASS scripts/ascs.py exists")
    else:
        print("FAIL scripts/ascs.py is missing")
        failures += 1
    for arm in ARMS.values():
        path = experiment_path(arm)
        if path.exists():
            print(f"PASS {arm.experiment_dir} exists")
        else:
            print(f"FAIL {arm.experiment_dir} is missing")
            failures += 1

    target_repo, status = ensure_target_repo(args.target_repo)
    if status:
        failures += 1
    else:
        print(f"PASS target repo exists and is a git work tree: {target_repo}")
        if ensure_clean(target_repo):
            failures += 1
        else:
            print("PASS target repo working tree is clean")

    proc = run_cmd(["python3", "scripts/ascs.py", "doctor"], root)
    if proc.returncode == 0:
        print("PASS python3 scripts/ascs.py doctor")
    else:
        print("FAIL python3 scripts/ascs.py doctor")
        failures += 1
    return 1 if failures else 0


def command_prepare_arm(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    target_repo, status = ensure_target_repo(args.target_repo)
    if status:
        return status
    assert target_repo is not None
    if ensure_clean(target_repo):
        return 1
    base_hash, status = resolve_commit(target_repo, args.base)
    if status:
        return status
    assert base_hash is not None
    if verify_pair_base(arm, base_hash):
        return 1
    if has_event(arm, "arm_start"):
        return fail(f"{arm.name} already has an arm_start event")
    if branch_exists(target_repo, arm.branch):
        return fail(f"target branch already exists: {arm.branch}")

    proc = run_git(target_repo, ["switch", "-c", arm.branch, base_hash])
    if not require_success(proc, f"git switch -c {arm.branch} {base_hash}"):
        return 1

    if arm.condition == "baseline":
        if verify_baseline_setup(target_repo):
            return 1
    else:
        if setup_treated(target_repo):
            return 1

    now = utc_now()
    amendment = f"{now} UTC. {AMENDMENT_NOTE}"
    if record_event(arm, "preregistration-amendment", amendment):
        return 1
    arm_start_note = (
        f"{now} UTC. arm_start; condition: {arm.condition}; task: {arm.task}; "
        f"branch: {arm.branch}; base commit: {base_hash}"
    )
    if record_event(arm, "arm_start", arm_start_note):
        return 1
    print("")
    print(build_prompt(arm, "first"), end="")
    return 0


def command_print_prompt(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    print(build_prompt(arm, args.phase), end="")
    return 0


def command_record_interruption(args: argparse.Namespace) -> int:
    missing = [
        name
        for name, present in (
            ("--visible-failure-seen", args.visible_failure_seen),
            ("--rejected-option-seen", args.rejected_option_seen),
            ("--libpg-rule-fired", args.libpg_rule_fired),
        )
        if not present
    ]
    if missing:
        print(
            "FAIL missing required observation flags: "
            + ", ".join(missing)
            + ". Do not record interruption_reached. This may be a void-pair condition.",
            file=sys.stderr,
        )
        return 1
    arm = arm_from_name(args.arm)
    note = (
        f"{utc_now()} UTC. interruption boundary reached: visible failure observed, "
        "rejected option observed, and the current checkpoint's libpg-backend "
        "target observed by operator (rule fired / stage tests green)."
    )
    return record_event(arm, "interruption_reached", note)


def command_record_resume_start(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    note = f"{utc_now()} UTC. resume prompt displayed to operator for immediate paste."
    status = record_event(arm, "resume-start", note)
    if status:
        return status
    print("")
    print(build_prompt(arm, "resume"), end="")
    print("")
    print(
        "注意: この resume prompt を即座に貼り付けてください。"
        "表示から貼り付けまでの遅延も測定区間に入ります。"
    )
    return 0


def command_record_first_progress_edit(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    note = f"{utc_now()} UTC. operator observed the first durable forward-progress edit."
    return record_event(arm, "first-progress-edit", note)


def command_finish_arm(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    finish_args = [
        "finish",
        "--experiment",
        arm.experiment_dir,
        "--missed-state-files",
        str(args.missed_state_files),
        "--repeated-failures",
        str(args.repeated_failures),
        "--rejected-option-relapses",
        str(args.rejected_option_relapses),
        "--human-corrections",
        str(args.human_corrections),
        "--recovery-quality",
        str(args.recovery_quality),
    ]
    status = run_ascs(finish_args)
    if status:
        return status
    return run_ascs(["score", "--experiment", arm.experiment_dir])


def command_status(args: argparse.Namespace) -> int:
    arm = arm_from_name(args.arm)
    path = events_path(arm)
    if not path.exists():
        return fail(f"events file does not exist: {path}")
    for event in load_events(arm):
        timestamp = event.get("timestamp", "<missing timestamp>")
        event_name = event.get("event", "<missing event>")
        print(f"{timestamp}\t{event_name}")
    return 0


def add_arm_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("arm", choices=sorted(ARMS))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Experiment 003 operator helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="check ASCS and target repo readiness")
    doctor_parser.add_argument("--target-repo", required=True)
    doctor_parser.set_defaults(func=command_doctor)

    prepare_parser = subparsers.add_parser("prepare-arm", help="create arm branch, set up condition, and record arm_start")
    add_arm_argument(prepare_parser)
    prepare_parser.add_argument("--target-repo", required=True)
    prepare_parser.add_argument("--base", required=True, help="target repo base commit for this arm")
    prepare_parser.set_defaults(func=command_prepare_arm)

    prompt_parser = subparsers.add_parser("print-prompt", help="print the Codex prompt without recording events")
    add_arm_argument(prompt_parser)
    prompt_parser.add_argument("--phase", required=True, choices=("first", "resume"))
    prompt_parser.set_defaults(func=command_print_prompt)

    interruption_parser = subparsers.add_parser("record-interruption", help="record interruption_reached after operator-observed boundary")
    add_arm_argument(interruption_parser)
    interruption_parser.add_argument("--visible-failure-seen", action="store_true")
    interruption_parser.add_argument("--rejected-option-seen", action="store_true")
    interruption_parser.add_argument("--libpg-rule-fired", action="store_true")
    interruption_parser.set_defaults(func=command_record_interruption)

    resume_parser = subparsers.add_parser("record-resume-start", help="record resume-start, then print the resume prompt")
    add_arm_argument(resume_parser)
    resume_parser.set_defaults(func=command_record_resume_start)

    first_edit_parser = subparsers.add_parser("record-first-progress-edit", help="record first-progress-edit")
    add_arm_argument(first_edit_parser)
    first_edit_parser.set_defaults(func=command_record_first_progress_edit)

    finish_parser = subparsers.add_parser("finish-arm", help="finish and score an arm using operator-judged metrics")
    add_arm_argument(finish_parser)
    finish_parser.add_argument(
        "--missed-state-files",
        required=True,
        type=int,
        help="Operator judgment from the session log; do not copy Codex self-report directly.",
    )
    finish_parser.add_argument(
        "--repeated-failures",
        required=True,
        type=int,
        help="Operator judgment from the session log; do not copy Codex self-report directly.",
    )
    finish_parser.add_argument(
        "--rejected-option-relapses",
        required=True,
        type=int,
        help="Operator judgment from the session log; do not copy Codex self-report directly.",
    )
    finish_parser.add_argument(
        "--human-corrections",
        required=True,
        type=int,
        help="Operator judgment from the session log; do not copy Codex self-report directly.",
    )
    finish_parser.add_argument(
        "--recovery-quality",
        required=True,
        type=int,
        choices=(0, 1, 2, 3, 4),
        help=(
            "Independent R1-R4 point total, 0-4. Count each satisfied rubric item; "
            "this is not a cumulative prefix score."
        ),
    )
    finish_parser.set_defaults(func=command_finish_arm)

    status_parser = subparsers.add_parser("status", help="list event timestamps and names")
    add_arm_argument(status_parser)
    status_parser.set_defaults(func=command_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
