#!/usr/bin/env python3
"""Lightweight measurement harness for Agent Session Control Stack.

This script intentionally does not start hooks, proxies, Codex, Claude Code, or
any upstream tool. It only checks repository shape and records manual
experiment data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = [
    "Active Plan",
    "Current Phase",
    "TaskList Summary",
    "Session Decisions",
    "Constraints and Blockers",
    "Worker Topology",
    "Skills Invoked",
    "Editing Files",
    "Failed Attempts",
    "Recovery Notes",
]

METRIC_KEYS = [
    "resume_time_seconds",
    "missed_state_files",
    "repeated_failures",
    "rejected_option_relapses",
    "human_corrections",
]

EXPERIMENT_004_METRIC_KEYS = [
    "resume_time_seconds",
    "missed_checkpoint_items",
    "missed_state_files",
    "human_corrections",
    "recovery_quality",
]

GATE_PROFILE_DEFAULT = "default"
GATE_PROFILE_EXPERIMENT_004 = "experiment-004"
GATE_PROFILES = (GATE_PROFILE_DEFAULT, GATE_PROFILE_EXPERIMENT_004)

# Reported for comparison, never gated on. Optional so that experiments
# recorded before it existed (001, 002) still score.
OPTIONAL_METRIC_KEYS = [
    "recovery_quality",
]

RESUME_START_EVENT = "resume-start"
FIRST_PROGRESS_EVENT = "first-progress-edit"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_slug() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_placeholder(content: str) -> bool:
    return (
        content.startswith("<!--")
        and content.endswith("-->")
        and content.count("<!--") == 1
    )


def report_section(existing_report: str | None, heading: str, next_heading: str | None) -> str | None:
    if not existing_report:
        return None
    start_marker = f"## {heading}"
    start = existing_report.find(start_marker)
    if start == -1:
        return None
    content_start = existing_report.find("\n", start)
    if content_start == -1:
        return None
    content_start += 1
    if next_heading:
        end = existing_report.find(f"\n## {next_heading}", content_start)
        if end == -1:
            return None
    else:
        end = len(existing_report)
    content = existing_report[content_start:end].strip()
    if is_placeholder(content):
        return None
    return content or None


def markdown_report(data: dict[str, Any], existing_report: str | None = None) -> str:
    metrics = data.get("metrics", {})
    score = data.get("score", {})
    task_summary = report_section(existing_report, "Task Summary", "Events")
    notes = report_section(existing_report, "Notes", None)
    lines = [
        "# Experiment Report",
        "",
        "## Metadata",
        "",
        f"- Name: `{data.get('name', '')}`",
        f"- Runtime: `{data.get('runtime', '')}`",
        f"- Target repo: `{data.get('target_repo', '')}`",
        f"- Created at: `{data.get('created_at', '')}`",
        "",
        "## Task Summary",
        "",
        task_summary
        or "<!-- Fill in the task, done definition, and stack condition before judging outcomes. -->",
        "",
        "## Events",
        "",
        "- See `events.jsonl`.",
        "",
        "## Result",
        "",
    ]

    if metrics:
        lines.extend(
            [
                "| Metric | Value |",
                "|---|---:|",
                f"| resume_time_seconds | {metrics.get('resume_time_seconds', '')} |",
                *(
                    [f"| missed_checkpoint_items | {metrics['missed_checkpoint_items']} |"]
                    if "missed_checkpoint_items" in metrics
                    else []
                ),
                f"| missed_state_files | {metrics.get('missed_state_files', '')} |",
                *(
                    [f"| repeated_failures | {metrics['repeated_failures']} |"]
                    if "repeated_failures" in metrics
                    else []
                ),
                *(
                    [f"| rejected_option_relapses | {metrics['rejected_option_relapses']} |"]
                    if "rejected_option_relapses" in metrics
                    else []
                ),
                f"| human_corrections | {metrics.get('human_corrections', '')} |",
            ]
        )
        if "recovery_quality" in metrics:
            lines.append(
                f"| recovery_quality (0-4, reported only) | {metrics['recovery_quality']} |"
            )
        lines.append("")
    else:
        lines.append("<!-- Filled by `scripts/ascs.py finish`. -->")
        lines.append("")

    if score:
        lines.extend(
            [
                f"Score: **{score.get('status', '')}**",
                "",
                f"Failed criteria: {score.get('failed_criteria_count', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Notes",
            "",
            notes or "<!-- One to three lines of qualitative observations. -->",
            "",
        ]
    )
    return "\n".join(lines)


def extract_sections(path: Path) -> list[str]:
    sections: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            sections.append(line.removeprefix("## ").strip())
    return sections


def check_checkpoint_sections(root: Path) -> tuple[str, str]:
    example_path = root / "examples/codex/.agent-session/state/checkpoint.md"
    template_path = root / "templates/state-file.md"
    existing = [path for path in (example_path, template_path) if path.exists()]
    if not existing:
        return "FAIL", "No checkpoint template found in examples/codex/.agent-session/state/checkpoint.md or templates/state-file.md"

    if example_path.exists():
        sections = extract_sections(example_path)
        if sections[: len(REQUIRED_SECTIONS)] == REQUIRED_SECTIONS:
            return "PASS", f"{example_path} has the required 10 sections in order"

    if template_path.exists():
        sections = extract_sections(template_path)
        if sections[: len(REQUIRED_SECTIONS)] == REQUIRED_SECTIONS:
            return "WARN", f"Using fallback {template_path}; example checkpoint template is missing or out of order"

    details = "; ".join(f"{path}: {extract_sections(path)}" for path in existing)
    return "FAIL", f"Checkpoint template sections are missing or out of order: {details}"


def doctor(args: argparse.Namespace) -> int:
    root = repo_root()
    results: list[tuple[str, str]] = []

    def exists(path_text: str) -> None:
        path = root / path_text
        if path.exists():
            results.append(("PASS", f"{path_text} exists"))
        else:
            results.append(("FAIL", f"{path_text} is missing"))

    exists("README.md")
    exists("ATTRIBUTION.md")
    exists("examples/codex/AGENTS.md")

    settings = root / "examples/claude-code/settings.example.json"
    if not settings.exists():
        results.append(("FAIL", "examples/claude-code/settings.example.json is missing"))
    else:
        try:
            read_json(settings)
            results.append(("PASS", "examples/claude-code/settings.example.json is valid JSON"))
        except (json.JSONDecodeError, ValueError) as exc:
            results.append(("FAIL", f"examples/claude-code/settings.example.json is invalid JSON: {exc}"))

    results.append(check_checkpoint_sections(root))

    for dirname in ("codex", "claude-code"):
        if (root / dirname).exists():
            results.append(("FAIL", f"top-level {dirname}/ must not exist"))
        else:
            results.append(("PASS", f"top-level {dirname}/ is absent"))

    fail_count = 0
    for status, message in results:
        if status == "FAIL":
            fail_count += 1
        print(f"{status} {message}")

    return 1 if fail_count else 0


def init_experiment(args: argparse.Namespace) -> int:
    root = repo_root()
    base_dir = root / "experiments"
    experiment_dir = base_dir / f"{today_slug()}-{args.name}"
    if experiment_dir.exists():
        print(f"FAIL {experiment_dir} already exists", file=sys.stderr)
        return 1

    experiment_dir.mkdir(parents=True)
    data = {
        "created_at": now_iso(),
        "name": args.name,
        "runtime": args.runtime,
        "target_repo": args.target_repo,
        "events_file": "events.jsonl",
        "report_file": "report.md",
        "gate_profile": args.gate_profile,
        "metrics": {},
        "score": {},
    }
    write_json(experiment_dir / "experiment.json", data)
    (experiment_dir / "events.jsonl").write_text("", encoding="utf-8")
    (experiment_dir / "report.md").write_text(markdown_report(data), encoding="utf-8")
    print(experiment_dir)
    return 0


def looks_like_non_utc_time(note: str) -> bool:
    """Heuristic: a clock time in a note that is not visibly UTC.

    Event timestamps are always UTC; clock times written into notes must be
    UTC too (Experiment 002 was corrected partly because notes mixed JST and
    UTC). Flag hh:mm:ss occurrences unless the note marks them as UTC/Z.
    """
    import re

    if not re.search(r"\b\d{1,2}:\d{2}:\d{2}\b", note):
        return False
    return not re.search(r"\b\d{1,2}:\d{2}:\d{2}(Z|\+00:00)|UTC", note)


def record_event(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    if not experiment_dir.exists():
        print(f"FAIL {experiment_dir} does not exist", file=sys.stderr)
        return 1

    if looks_like_non_utc_time(args.note):
        print(
            "WARN note contains a clock time without a UTC marker; "
            "write note times in UTC (append Z or +00:00, or say UTC) — "
            "mixed timezones forced the Experiment 002 correction"
        )

    event = {
        "timestamp": now_iso(),
        "event": args.event,
        "note": args.note,
    }
    events_path = experiment_dir / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    print(f"PASS recorded {args.event} in {events_path}")
    return 0


def metric_as_int(metrics: dict[str, Any], key: str) -> int:
    value = metrics[key]
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer, got boolean")
    if isinstance(value, int):
        return value
    return int(value)


def parse_count_or_na(value: str) -> int | str:
    if value.lower() in {"n/a", "na"}:
        return "n/a"
    return int(value)


def failed_criteria(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if metrics["missed_state_files"] != 0:
        failures.append("missed_state_files != 0")
    if metric_as_int(metrics, "repeated_failures") != 0:
        failures.append("repeated_failures != 0")
    if metric_as_int(metrics, "rejected_option_relapses") != 0:
        failures.append("rejected_option_relapses != 0")
    if metric_as_int(metrics, "human_corrections") > 1:
        failures.append("human_corrections > 1")
    return failures


def status_for_metrics(
    metrics: dict[str, Any],
    gate_profile: str = GATE_PROFILE_DEFAULT,
) -> dict[str, Any]:
    if gate_profile == GATE_PROFILE_EXPERIMENT_004:
        return {
            "status": "REPORTED_ONLY",
            "failed_criteria": [],
            "failed_criteria_count": 0,
            "scored_at": now_iso(),
            "gate_profile": gate_profile,
        }

    failures = failed_criteria(metrics)
    if not failures:
        status = "PASS"
    elif len(failures) <= 2:
        status = "PARTIAL"
    else:
        status = "FAIL"
    return {
        "status": status,
        "failed_criteria": failures,
        "failed_criteria_count": len(failures),
        "scored_at": now_iso(),
        "gate_profile": gate_profile,
    }


def calculate_score(
    metrics: dict[str, Any],
    scored_at: str | None = None,
    gate_profile: str = GATE_PROFILE_DEFAULT,
) -> dict[str, Any]:
    score = status_for_metrics(metrics, gate_profile)
    if scored_at is not None:
        score["scored_at"] = scored_at
    return score


def derive_resume_time(events_path: Path) -> tuple[int | None, str]:
    """Derive resume_time_seconds from recorded events.

    Uses the LAST `resume-start` event (an aborted resume attempt is
    superseded by recording a fresh `resume-start`) and the first
    `first-progress-edit` event after it. Returns (seconds, detail) or
    (None, reason).
    """
    if not events_path.exists():
        return None, f"{events_path} does not exist"
    resume_start = None
    first_progress = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == RESUME_START_EVENT:
            resume_start = event["timestamp"]
            first_progress = None
        elif event.get("event") == FIRST_PROGRESS_EVENT and resume_start and not first_progress:
            first_progress = event["timestamp"]
    if resume_start is None:
        return None, f"no `{RESUME_START_EVENT}` event recorded"
    if first_progress is None:
        return None, f"no `{FIRST_PROGRESS_EVENT}` event recorded after the last `{RESUME_START_EVENT}`"
    delta = datetime.fromisoformat(first_progress) - datetime.fromisoformat(resume_start)
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return None, f"`{FIRST_PROGRESS_EVENT}` precedes `{RESUME_START_EVENT}`"
    return seconds, f"{resume_start} -> {first_progress}"


def finish_experiment(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    experiment_json = experiment_dir / "experiment.json"
    if not experiment_json.exists():
        print(f"FAIL {experiment_json} does not exist", file=sys.stderr)
        return 1

    derived, detail = derive_resume_time(experiment_dir / "events.jsonl")
    if derived is None and args.resume_time is None:
        print(
            f"FAIL cannot determine resume_time_seconds: {detail}. "
            f"Record `{RESUME_START_EVENT}` when the first resume prompt is sent and "
            f"`{FIRST_PROGRESS_EVENT}` at the first forward-progress edit "
            "(the clock never starts at an interruption event or a restart decision)",
            file=sys.stderr,
        )
        return 1
    if derived is not None and args.resume_time is not None and abs(derived - args.resume_time) > 2:
        print(
            f"FAIL --resume-time {args.resume_time} disagrees with the event-derived value "
            f"{derived} ({detail}); the event-derived value is authoritative — drop --resume-time "
            "or fix the recorded events",
            file=sys.stderr,
        )
        return 1
    resume_time = derived if derived is not None else args.resume_time
    if derived is not None:
        print(f"PASS resume_time_seconds={derived} derived from events ({detail})")
    else:
        print(
            f"WARN resume_time_seconds={resume_time} taken from --resume-time without "
            f"`{RESUME_START_EVENT}`/`{FIRST_PROGRESS_EVENT}` events; event-derived timing is required "
            "for before/after pairs (experiments/README.md)"
        )

    data = read_json(experiment_json)
    gate_profile = args.gate_profile
    data_gate_profile = data.get("gate_profile")
    if data_gate_profile in GATE_PROFILES and args.gate_profile == GATE_PROFILE_DEFAULT:
        gate_profile = data_gate_profile

    if gate_profile == GATE_PROFILE_DEFAULT and args.missed_state_files == "n/a":
        print(
            "FAIL --missed-state-files n/a is only valid with --gate-profile experiment-004",
            file=sys.stderr,
        )
        return 1
    if gate_profile == GATE_PROFILE_DEFAULT and (
        args.repeated_failures is None or args.rejected_option_relapses is None
    ):
        print(
            "FAIL --repeated-failures and --rejected-option-relapses are required "
            "with the default gate profile",
            file=sys.stderr,
        )
        return 1
    if gate_profile == GATE_PROFILE_EXPERIMENT_004 and (
        args.missed_checkpoint_items is None or args.recovery_quality is None
    ):
        print(
            "FAIL --missed-checkpoint-items and --recovery-quality are required "
            "with --gate-profile experiment-004",
            file=sys.stderr,
        )
        return 1

    metrics: dict[str, Any] = {
        "resume_time_seconds": resume_time,
        "missed_state_files": args.missed_state_files,
        "human_corrections": args.human_corrections,
    }
    if args.repeated_failures is not None:
        metrics["repeated_failures"] = args.repeated_failures
    if args.rejected_option_relapses is not None:
        metrics["rejected_option_relapses"] = args.rejected_option_relapses
    if args.missed_checkpoint_items is not None:
        metrics["missed_checkpoint_items"] = args.missed_checkpoint_items
    if args.recovery_quality is not None:
        metrics["recovery_quality"] = args.recovery_quality
    data["metrics"] = metrics
    data["gate_profile"] = gate_profile
    data["finished_at"] = now_iso()
    data["score"] = calculate_score(metrics, gate_profile=gate_profile)
    write_json(experiment_json, data)
    report_path = experiment_dir / "report.md"
    existing_report = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    if report_section(existing_report, "Task Summary", "Events") is None:
        print(
            "WARN Task Summary in report.md is empty or still a placeholder; "
            "judgment criteria should be written before finishing "
            "(docs/measurement-plan.md)"
        )
    report_path.write_text(markdown_report(data, existing_report), encoding="utf-8")
    print(f"PASS finished {experiment_dir}")
    return 0


def score_experiment(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    experiment_json = experiment_dir / "experiment.json"
    if not experiment_json.exists():
        print(f"FAIL {experiment_json} does not exist", file=sys.stderr)
        return 1

    data = read_json(experiment_json)
    metrics = data.get("metrics", {})
    gate_profile = data.get("gate_profile", GATE_PROFILE_DEFAULT)
    if gate_profile not in GATE_PROFILES:
        print(f"FAIL unknown gate_profile: {gate_profile}", file=sys.stderr)
        return 1
    required_keys = (
        EXPERIMENT_004_METRIC_KEYS
        if gate_profile == GATE_PROFILE_EXPERIMENT_004
        else METRIC_KEYS
    )
    missing = [key for key in required_keys if key not in metrics]
    if missing:
        print(f"FAIL missing metrics: {', '.join(missing)}", file=sys.stderr)
        return 1

    typed_metrics: dict[str, Any] = {}
    for key in required_keys:
        if key == "missed_state_files" and metrics[key] == "n/a":
            typed_metrics[key] = "n/a"
        else:
            typed_metrics[key] = int(metrics[key])
    existing_score = data.get("score", {})
    existing_scored_at = existing_score.get("scored_at") if isinstance(existing_score, dict) else None
    score = calculate_score(typed_metrics, existing_scored_at, gate_profile)

    print("| Metric | Value | Criterion |")
    print("|---|---:|---|")
    if gate_profile == GATE_PROFILE_EXPERIMENT_004:
        print(f"| missed_checkpoint_items | {typed_metrics['missed_checkpoint_items']} | reported only; pair-verdict compares |")
        print(f"| human_corrections | {typed_metrics['human_corrections']} | reported only; pair-verdict compares |")
        print(f"| recovery_quality | {typed_metrics['recovery_quality']} | reported only; pair-verdict compares |")
        print(f"| missed_state_files | {typed_metrics['missed_state_files']} | treated-only protocol adherence |")
        print(f"| resume_time_seconds | {typed_metrics['resume_time_seconds']} | reported only |")
    else:
        print(f"| missed_state_files | {typed_metrics['missed_state_files']} | must be 0 |")
        print(f"| repeated_failures | {typed_metrics['repeated_failures']} | must be 0 |")
        print(f"| rejected_option_relapses | {typed_metrics['rejected_option_relapses']} | must be 0 |")
        print(f"| human_corrections | {typed_metrics['human_corrections']} | must be <= 1 |")
        print(f"| resume_time_seconds | {typed_metrics['resume_time_seconds']} | reported only |")
    if "recovery_quality" in metrics and gate_profile != GATE_PROFILE_EXPERIMENT_004:
        print(f"| recovery_quality | {int(metrics['recovery_quality'])} | reported only (0-4) |")
    print("")
    print(f"Score: **{score['status']}**")
    if score["failed_criteria"]:
        print("")
        print("Failed criteria:")
        for failure in score["failed_criteria"]:
            print(f"- {failure}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Session Control Stack measurement harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="check repository measurement harness readiness")
    doctor_parser.set_defaults(func=doctor)

    init_parser = subparsers.add_parser("init", help="create an experiment directory")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--runtime", required=True, choices=("codex", "claude-code"))
    init_parser.add_argument("--target-repo", required=True)
    init_parser.add_argument("--gate-profile", choices=GATE_PROFILES, default=GATE_PROFILE_DEFAULT)
    init_parser.set_defaults(func=init_experiment)

    record_parser = subparsers.add_parser("record", help="append an event to events.jsonl")
    record_parser.add_argument("--experiment", required=True)
    record_parser.add_argument("--event", required=True)
    record_parser.add_argument("--note", required=True)
    record_parser.set_defaults(func=record_event)

    finish_parser = subparsers.add_parser("finish", help="save final metrics and update report.md")
    finish_parser.add_argument("--experiment", required=True)
    finish_parser.add_argument(
        "--resume-time",
        type=int,
        default=None,
        dest="resume_time",
        help="cross-check only; resume_time_seconds is derived from "
        "resume-start/first-progress-edit events when they exist",
    )
    finish_parser.add_argument("--gate-profile", choices=GATE_PROFILES, default=GATE_PROFILE_DEFAULT)
    finish_parser.add_argument("--missed-checkpoint-items", type=int, default=None)
    finish_parser.add_argument("--missed-state-files", required=True, type=parse_count_or_na)
    finish_parser.add_argument("--repeated-failures", type=int, default=None)
    finish_parser.add_argument("--rejected-option-relapses", type=int, default=None)
    finish_parser.add_argument("--human-corrections", required=True, type=int)
    finish_parser.add_argument(
        "--recovery-quality",
        type=int,
        choices=(0, 1, 2, 3, 4),
        default=None,
        help="R1-R4 rubric total (reported for comparison, never gated)",
    )
    finish_parser.set_defaults(func=finish_experiment)

    score_parser = subparsers.add_parser("score", help="score an experiment")
    score_parser.add_argument("--experiment", required=True)
    score_parser.set_defaults(func=score_experiment)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
