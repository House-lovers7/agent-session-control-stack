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
                f"| missed_state_files | {metrics.get('missed_state_files', '')} |",
                f"| repeated_failures | {metrics.get('repeated_failures', '')} |",
                f"| rejected_option_relapses | {metrics.get('rejected_option_relapses', '')} |",
                f"| human_corrections | {metrics.get('human_corrections', '')} |",
                "",
            ]
        )
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
        "metrics": {},
        "score": {},
    }
    write_json(experiment_dir / "experiment.json", data)
    (experiment_dir / "events.jsonl").write_text("", encoding="utf-8")
    (experiment_dir / "report.md").write_text(markdown_report(data), encoding="utf-8")
    print(experiment_dir)
    return 0


def record_event(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    if not experiment_dir.exists():
        print(f"FAIL {experiment_dir} does not exist", file=sys.stderr)
        return 1

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


def failed_criteria(metrics: dict[str, int]) -> list[str]:
    failures: list[str] = []
    if metrics["missed_state_files"] != 0:
        failures.append("missed_state_files != 0")
    if metrics["repeated_failures"] != 0:
        failures.append("repeated_failures != 0")
    if metrics["rejected_option_relapses"] != 0:
        failures.append("rejected_option_relapses != 0")
    if metrics["human_corrections"] > 1:
        failures.append("human_corrections > 1")
    return failures


def status_for_metrics(metrics: dict[str, int]) -> dict[str, Any]:
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
    }


def calculate_score(metrics: dict[str, int], scored_at: str | None = None) -> dict[str, Any]:
    score = status_for_metrics(metrics)
    if scored_at is not None:
        score["scored_at"] = scored_at
    return score


def finish_experiment(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    experiment_json = experiment_dir / "experiment.json"
    if not experiment_json.exists():
        print(f"FAIL {experiment_json} does not exist", file=sys.stderr)
        return 1

    data = read_json(experiment_json)
    metrics = {
        "resume_time_seconds": args.resume_time,
        "missed_state_files": args.missed_state_files,
        "repeated_failures": args.repeated_failures,
        "rejected_option_relapses": args.rejected_option_relapses,
        "human_corrections": args.human_corrections,
    }
    data["metrics"] = metrics
    data["finished_at"] = now_iso()
    data["score"] = calculate_score(metrics)
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
    missing = [key for key in METRIC_KEYS if key not in metrics]
    if missing:
        print(f"FAIL missing metrics: {', '.join(missing)}", file=sys.stderr)
        return 1

    typed_metrics = {key: int(metrics[key]) for key in METRIC_KEYS}
    existing_score = data.get("score", {})
    existing_scored_at = existing_score.get("scored_at") if isinstance(existing_score, dict) else None
    score = calculate_score(typed_metrics, existing_scored_at)

    print("| Metric | Value | Criterion |")
    print("|---|---:|---|")
    print(f"| missed_state_files | {typed_metrics['missed_state_files']} | must be 0 |")
    print(f"| repeated_failures | {typed_metrics['repeated_failures']} | must be 0 |")
    print(f"| rejected_option_relapses | {typed_metrics['rejected_option_relapses']} | must be 0 |")
    print(f"| human_corrections | {typed_metrics['human_corrections']} | must be <= 1 |")
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
    init_parser.set_defaults(func=init_experiment)

    record_parser = subparsers.add_parser("record", help="append an event to events.jsonl")
    record_parser.add_argument("--experiment", required=True)
    record_parser.add_argument("--event", required=True)
    record_parser.add_argument("--note", required=True)
    record_parser.set_defaults(func=record_event)

    finish_parser = subparsers.add_parser("finish", help="save final metrics and update report.md")
    finish_parser.add_argument("--experiment", required=True)
    finish_parser.add_argument("--resume-time", required=True, type=int, dest="resume_time")
    finish_parser.add_argument("--missed-state-files", required=True, type=int)
    finish_parser.add_argument("--repeated-failures", required=True, type=int)
    finish_parser.add_argument("--rejected-option-relapses", required=True, type=int)
    finish_parser.add_argument("--human-corrections", required=True, type=int)
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
