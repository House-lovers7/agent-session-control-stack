#!/usr/bin/env python3
"""Lightweight measurement harness for Agent Session Control Stack.

This script intentionally does not start hooks, proxies, Codex, Claude Code, or
any upstream tool. It only checks repository shape and records manual
experiment data.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
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
GATE_PROFILE_EXPERIMENT_005 = "experiment-005"
GATE_PROFILES = (
    GATE_PROFILE_DEFAULT,
    GATE_PROFILE_EXPERIMENT_004,
    GATE_PROFILE_EXPERIMENT_005,
)
# Profiles that apply no absolute per-arm gate: metrics are reported only and
# comparisons happen through the experiment helper's pair-verdict command.
REPORTED_ONLY_GATE_PROFILES = frozenset(
    {GATE_PROFILE_EXPERIMENT_004, GATE_PROFILE_EXPERIMENT_005}
)

# Reported for comparison, never gated on. Optional so that experiments
# recorded before it existed (001, 002) still score.
OPTIONAL_METRIC_KEYS = [
    "recovery_quality",
]

RESUME_START_EVENT = "resume-start"
FIRST_PROGRESS_EVENT = "first-progress-edit"
RESUME_ABORT_EVENT = "resume-attempt-aborted"

EVENT_SCHEMA_VERSION = 1
EVENT_FILE_LIMIT = 10 * 1024 * 1024
EVENT_ALLOWED_FIELDS = {
    "schema_version",
    "timestamp",
    "event",
    "note",
    "pair_id",
    "condition",
    "transaction_id",
}
EVENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,99}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EXPERIMENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ARM_CONDITION_RE = re.compile(r"(?:^|[-_.])(baseline|treated)(?:[-_.]|$)")
LAYER_EVENT_DELIMITERS = r"[-_:/\.]"

EXPERIMENT_004_PAIRS = {
    "1": (
        "2026-07-06-claude-code-restart-004-p1-baseline",
        "2026-07-06-claude-code-restart-004-p1-treated",
    ),
    "2": (
        "2026-07-06-claude-code-restart-004-p2-treated",
        "2026-07-06-claude-code-restart-004-p2-baseline",
    ),
}
EXPERIMENT_004_CLOSEOUT = "2026-07-06-claude-code-restart-004-closeout.md"
PROTECTED_EVIDENCE_FILENAMES = {"events.jsonl", "report.md", "experiment.json"}

# Claim-boundary layer model. ASCS integrates three upstream projects as
# independent layer contracts; it bundles none of their code. The verdict
# engine states what can and cannot be claimed about each layer in
# isolation, and separately about the full-stack composition.
CLAIM_LAYERS = {
    "compression": {
        "upstream": "pxpipe (teamchong)",
        "role": "reduce bulky input context via image/compressed representations",
        "event_markers": ("compression", "pxpipe"),
        "risks": [
            "Lossy compression can silently misread or confabulate content.",
            "Byte-exact values (hashes, IDs, secrets, paths, migration names, deploy targets) are corrupted if compressed.",
        ],
        "required_evidence": [
            "Round-trip fidelity evidence for the specific compressed content type.",
            "Token/bill reduction recorded as events, kept separate from correctness evidence.",
        ],
        "disallowed_without_evidence": [
            "Token or bill reduction implies semantic correctness.",
            "Compression is safe for byte-exact values.",
        ],
    },
    "health_detection": {
        "upstream": "claude-code-session-health (House-lovers7)",
        "role": "detect session health degradation and let the model propose interventions",
        "event_markers": ("health", "session-health"),
        "risks": [
            "False positives trigger unnecessary interventions.",
            "False negatives miss real degradation.",
            "Detection is conflated with recovery.",
        ],
        "required_evidence": [
            "Intervention-timing events linking a detection to a recorded intervention.",
        ],
        "disallowed_without_evidence": [
            "Health detection by itself improved productivity.",
            "Detection accuracy claims without labeled detection events.",
        ],
    },
    "checkpoint_recovery": {
        "upstream": "compact-plus (u-ichi)",
        "role": "preserve state before compaction and inject recovery guidance after it",
        "event_markers": (
            "compact-plus",
            "compact_plus",
            "compactplus",
            "state-capture",
            "recovery-injection",
        ),
        "risks": [
            "Incomplete checkpoint state (failed attempts or decisions missing).",
            "Stale recovery assumptions after the repo moved on.",
            "Summary treated as source of truth instead of hypothesis.",
        ],
        "required_evidence": [
            "Explicit compact-plus state-capture and recovery-injection runtime events.",
            "Evidence that plan, decisions, failed attempts, and checkpoint state were preserved and used in recovery.",
        ],
        "disallowed_without_evidence": [
            "compact-plus runtime recovery claims without compact-plus runtime events.",
            "Recovery quality claims without preserved-and-used checkpoint evidence.",
        ],
    },
}

COMPOSITION_DISALLOWED_CLAIMS = [
    "Running all three layers together improves productivity.",
    "The full-stack composition effect is validated.",
    "Single-layer results transfer additively to the composition.",
]

COMPOSITION_RISKS = [
    "Failure attribution is ambiguous when layers interact.",
    "Two compact deciders (health detection and the checkpoint reminder) can conflict without a single-decider rule.",
]

COMPOSITION_REQUIRED_EVIDENCE = [
    "Isolated, valid, non-void evidence for each layer first.",
    "A pre-registered full-stack vs single-layer comparison with valid pairs.",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_slug() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def nonnegative_int(value: str | int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if isinstance(value, bool) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def safe_experiment_name(value: str) -> str:
    if not isinstance(value, str) or not EXPERIMENT_NAME_RE.fullmatch(value) or ".." in value:
        raise argparse.ArgumentTypeError(
            "experiment name must start with an alphanumeric character, contain only "
            "ASCII letters, digits, '.', '_', or '-', be at most 80 characters, and not contain '..'"
        )
    return value


def parse_utc_timestamp(value: Any, context: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}: timestamp must be a non-empty string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{context}: timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{context}: timestamp must include a UTC offset")
    return parsed


def validate_event_record(
    event: Any,
    *,
    allow_legacy: bool = False,
    context: str = "event",
) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError(f"{context}: event must be a JSON object")
    version = event.get("schema_version")
    legacy = version is None
    if legacy:
        if not allow_legacy:
            raise ValueError(
                f"{context}: legacy event has no schema_version; pass allow_legacy=True explicitly"
            )
    elif isinstance(version, bool) or version != EVENT_SCHEMA_VERSION:
        raise ValueError(
            f"{context}: unsupported schema_version {version!r}; expected {EVENT_SCHEMA_VERSION}"
        )

    unknown_fields = set(event) - EVENT_ALLOWED_FIELDS
    if unknown_fields:
        raise ValueError(f"{context}: event contains {len(unknown_fields)} unknown field(s)")

    parse_utc_timestamp(event.get("timestamp"), context)
    event_name = event.get("event")
    if not isinstance(event_name, str) or not EVENT_NAME_RE.fullmatch(event_name):
        raise ValueError(f"{context}: event must be a 1-100 character safe event name")
    note = event.get("note")
    if not isinstance(note, str) or len(note) > 8192 or (not legacy and not note):
        raise ValueError(
            f"{context}: note must be a string of at most 8192 characters "
            "(non-empty for schema_version 1)"
        )
    if any(ord(char) < 32 and char != "\t" for char in note):
        raise ValueError(f"{context}: note must not contain control characters or newlines")

    for field in ("pair_id", "transaction_id"):
        if field in event and (
            not isinstance(event[field], str) or not EVENT_ID_RE.fullmatch(event[field])
        ):
            raise ValueError(f"{context}: {field} must be a safe 1-64 character identifier")
    if "condition" in event and event["condition"] not in {"baseline", "treated"}:
        raise ValueError(f"{context}: condition must be baseline or treated")
    return dict(event)


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


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
    try:
        name = safe_experiment_name(args.name)
    except argparse.ArgumentTypeError as exc:
        print(f"FAIL invalid experiment name: {exc}", file=sys.stderr)
        return 1
    base_dir = (root / "experiments").resolve()
    experiment_dir = (base_dir / f"{today_slug()}-{name}").resolve(strict=False)
    if experiment_dir.parent != base_dir:
        print("FAIL invalid experiment name: resolved path escapes experiments/", file=sys.stderr)
        return 1
    if experiment_dir.exists():
        print(f"FAIL {experiment_dir} already exists", file=sys.stderr)
        return 1

    experiment_dir.mkdir(parents=True)
    data = {
        "created_at": now_iso(),
        "name": name,
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
    if not experiment_dir.is_dir():
        print(f"FAIL {experiment_dir} is not an experiment directory", file=sys.stderr)
        return 1

    if looks_like_non_utc_time(args.note):
        print(
            "WARN note contains a clock time without a UTC marker; "
            "write note times in UTC (append Z or +00:00, or say UTC) — "
            "mixed timezones forced the Experiment 002 correction"
        )

    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "timestamp": now_iso(),
        "event": args.event,
        "note": args.note,
    }
    for field in ("pair_id", "condition", "transaction_id"):
        value = getattr(args, field, None)
        if value is not None:
            event[field] = value
    try:
        validate_event_record(event)
    except ValueError as exc:
        print(f"FAIL invalid event: {exc}", file=sys.stderr)
        return 1
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
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        parsed = int(value)
    else:
        raise ValueError(f"{key} must be an integer")
    if parsed < 0:
        raise ValueError(f"{key} must be non-negative")
    return parsed


def parse_count_or_na(value: str) -> int | str:
    if value.lower() in {"n/a", "na"}:
        return "n/a"
    return nonnegative_int(value)


def failed_criteria(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if metric_as_int(metrics, "missed_state_files") != 0:
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
    required = (
        EXPERIMENT_004_METRIC_KEYS
        if gate_profile in REPORTED_ONLY_GATE_PROFILES
        else METRIC_KEYS
    )
    for key in required:
        if key == "missed_state_files" and metrics.get(key) == "n/a":
            if gate_profile not in REPORTED_ONLY_GATE_PROFILES:
                raise ValueError(
                    "missed_state_files=n/a is only valid for experiment-004/005"
                )
            continue
        metric_as_int(metrics, key)
    if "recovery_quality" in metrics and metric_as_int(metrics, "recovery_quality") > 4:
        raise ValueError("recovery_quality must be between 0 and 4")

    if gate_profile in REPORTED_ONLY_GATE_PROFILES:
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

    Uses the LAST `resume-start` event and the first `first-progress-edit`
    after it. `resume-attempt-aborted` clears the attempt; only a fresh
    `resume-start` can begin another clock. Returns (seconds, detail) or
    (None, reason).
    """
    if not events_path.exists():
        return None, f"{events_path} does not exist"
    return derive_resume_time_from_events(
        read_events(events_path, allow_legacy=True), allow_legacy=True
    )


def derive_resume_time_from_events(
    events: list[dict[str, Any]], *, allow_legacy: bool = False
) -> tuple[int | None, str]:
    """Explicit resume/abort/progress state machine over validated events."""
    resume_start = None
    first_progress = None
    aborted_since_start = False
    try:
        validated = [
            validate_event_record(event, allow_legacy=allow_legacy, context=f"event[{index}]")
            for index, event in enumerate(events)
        ]
    except ValueError as exc:
        return None, f"invalid event evidence: {exc}"
    for event in validated:
        event_name = event["event"]
        if event_name == RESUME_START_EVENT:
            resume_start = event["timestamp"]
            first_progress = None
            aborted_since_start = False
        elif event_name == RESUME_ABORT_EVENT:
            resume_start = None
            first_progress = None
            aborted_since_start = True
        elif event_name == FIRST_PROGRESS_EVENT and resume_start and not first_progress:
            first_progress = event["timestamp"]
    if resume_start is None:
        if aborted_since_start:
            return None, f"`{RESUME_ABORT_EVENT}` requires a fresh `{RESUME_START_EVENT}`"
        return None, f"no `{RESUME_START_EVENT}` event recorded"
    if first_progress is None:
        return None, f"no `{FIRST_PROGRESS_EVENT}` event recorded after the last `{RESUME_START_EVENT}`"
    delta = parse_utc_timestamp(first_progress, FIRST_PROGRESS_EVENT) - parse_utc_timestamp(
        resume_start, RESUME_START_EVENT
    )
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return None, f"`{FIRST_PROGRESS_EVENT}` precedes `{RESUME_START_EVENT}`"
    return seconds, f"{resume_start} -> {first_progress}"


def read_events(events_path: Path, *, allow_legacy: bool = False) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not events_path.exists():
        return events
    if events_path.stat().st_size > EVENT_FILE_LIMIT:
        raise ValueError(f"{events_path}: events file exceeds {EVENT_FILE_LIMIT} bytes")
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line, object_pairs_hook=reject_duplicate_json_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{events_path}:{line_number}: invalid or ambiguous JSON") from exc
        events.append(
            validate_event_record(
                event,
                allow_legacy=allow_legacy,
                context=f"{events_path}:{line_number}",
            )
        )
    return events


def has_event(events: list[dict[str, Any]], event_name: str) -> bool:
    return any(event.get("event") == event_name for event in events)


def event_notes(events: list[dict[str, Any]], event_name: str) -> list[str]:
    return [str(event.get("note", "")) for event in events if event.get("event") == event_name]


def event_note_field(event: dict[str, Any], field: str) -> str | None:
    note = str(event.get("note", ""))
    match = re.search(rf"(?:^|;\s*){re.escape(field)}=([^;]+)", note)
    return match.group(1).strip() if match else None


def transaction_ids(
    events: list[dict[str, Any]], event_name: str, target_event: str | None = None
) -> set[str]:
    result = set()
    for event in events:
        if event.get("event") != event_name:
            continue
        if target_event is not None and event_note_field(event, "target_event") != target_event:
            continue
        transaction_id = event_note_field(event, "txid")
        if transaction_id:
            result.add(transaction_id)
    return result


def has_committed_pair_event(
    arm_events: dict[str, list[dict[str, Any]]], event_name: str
) -> bool:
    if all(
        any(
            event.get("event") == event_name and event_note_field(event, "txid") is None
            for event in events
        )
        for events in arm_events.values()
    ):
        return True
    committed_ids: set[str] | None = None
    for events in arm_events.values():
        arm_ids = transaction_ids(events, event_name)
        arm_ids &= transaction_ids(events, "pair-event-commit", event_name)
        committed_ids = arm_ids if committed_ids is None else committed_ids & arm_ids
    return bool(committed_ids)


def has_pending_pair_event(
    arm_events: dict[str, list[dict[str, Any]]], event_name: str
) -> bool:
    untagged = [
        any(
            event.get("event") == event_name and event_note_field(event, "txid") is None
            for event in events
        )
        for events in arm_events.values()
    ]
    if any(untagged) and not all(untagged):
        return True
    all_ids = set()
    for events in arm_events.values():
        all_ids |= transaction_ids(events, event_name)
        for stage in ("pair-event-prepare", "pair-event-commit", "pair-event-abort"):
            all_ids |= transaction_ids(events, stage, event_name)
    for transaction_id in all_ids:
        if not all(
            transaction_id in transaction_ids(events, event_name)
            and transaction_id in transaction_ids(
                events, "pair-event-commit", event_name
            )
            for events in arm_events.values()
        ):
            return True
    return False


def void_condition(events: list[dict[str, Any]]) -> str | None:
    for note in event_notes(events, "void-pair"):
        match = re.search(r"\bcondition=([^;\s]+)", note)
        if match:
            return match.group(1)
    return None


def has_scope_differs_event(events: list[dict[str, Any]]) -> bool:
    return any("scope_differs=True" in note for note in event_notes(events, "pair-checkpoint-audit"))


def failing_count(events: list[dict[str, Any]]) -> int | None:
    for note in event_notes(events, "interruption_reached"):
        match = re.search(r"\bfailing_count=(\d+)", note)
        if match:
            return int(match.group(1))
    return None


def arm_condition(arm_name: str, events: list[dict[str, Any]]) -> str | None:
    conditions = set(ARM_CONDITION_RE.findall(arm_name.lower()))
    conditions.update(
        str(event["condition"])
        for event in events
        if event.get("event") == "arm_start" and "condition" in event
    )
    return next(iter(conditions)) if len(conditions) == 1 else None


def lifecycle_positions(events: list[dict[str, Any]]) -> tuple[int | None, int | None, int | None]:
    start = next((index for index, event in enumerate(events) if event["event"] == "arm_start"), None)
    checkpoint = next(
        (
            index
            for index, event in enumerate(events)
            if event["event"] == "interruption_reached" and start is not None and index > start
        ),
        None,
    )
    verdict = next(
        (
            index
            for index in range(len(events) - 1, -1, -1)
            if events[index]["event"] == "pair-verdict"
        ),
        None,
    )
    return start, checkpoint, verdict


def pair_verdict_signature(
    pair: str,
    condition: str,
    events: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    verdicts = [event for event in events if event["event"] == "pair-verdict"]
    if not verdicts:
        return None, "missing pair-verdict"
    verdict = verdicts[-1]
    note = " ".join(verdict["note"].split())
    if not note:
        return None, "empty pair-verdict note"
    if verdict.get("pair_id") not in {None, pair}:
        return None, "pair-verdict pair_id does not match its pair"
    note_pair = re.search(r"(?:^|[;\s])pair\s*[=:]\s*([A-Za-z0-9._-]+)", note)
    if note_pair and note_pair.group(1) != pair:
        return None, "pair-verdict note names a different pair"
    if verdict.get("condition") not in {None, condition}:
        return None, "pair-verdict condition does not match its arm"
    signature = json.dumps(
        {
            "note": note,
            "pair_id": verdict.get("pair_id"),
            "transaction_id": verdict.get("transaction_id"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return signature, None


def pair_verdict(pair: str, arm_events: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pure per-pair claim-boundary classification over parsed events."""
    all_events = [event for events in arm_events.values() for event in events]
    condition = void_condition(all_events)
    scope_differs = has_scope_differs_event(all_events)
    started = {arm: has_event(events, "arm_start") for arm, events in arm_events.items()}
    checkpointed = {arm: has_event(events, "interruption_reached") for arm, events in arm_events.items()}
    conditions = {arm: arm_condition(arm, events) for arm, events in arm_events.items()}
    valid_arm_shape = len(arm_events) == 2 and set(conditions.values()) == {"baseline", "treated"}
    failing_counts = {arm: failing_count(events) for arm, events in arm_events.items()}
    verdict_committed = has_committed_pair_event(arm_events, "pair-verdict")
    verdict_pending = has_pending_pair_event(arm_events, "pair-verdict")
    resume_time = {}
    for arm, events in arm_events.items():
        seconds, detail = derive_resume_time_from_events(events, allow_legacy=True)
        resume_time[arm] = {"seconds": seconds, "trusted": seconds is not None, "detail": detail}

    reasons = []
    if condition:
        status = f"VOID condition {condition}"
        claim_boundary = "void pair; no treated-vs-baseline claim"
        reasons.append(f"Pair {pair} has an explicit void-pair event (condition {condition}).")
    elif scope_differs:
        # An operator scope_differs judgment is strong evidence on its own:
        # fail closed and void the pair even before a void-pair event lands.
        status = "VOID (scope_differs audit)"
        claim_boundary = "operator scope_differs judgment; no treated-vs-baseline claim"
        reasons.append(
            f"Pair {pair} has a pair-checkpoint-audit event with scope_differs=True; "
            "the operator judgment voids the pair even without a recorded void-pair event."
        )
    elif not any(started.values()):
        status = "NOT RUN"
        claim_boundary = "incomplete pair; not a failure"
        reasons.append(f"Pair {pair} arms were never started; an unrun pair is not failure evidence.")
    elif len(arm_events) < 2:
        status = "INCOMPLETE"
        claim_boundary = "single-arm evidence; no comparison"
        reasons.append(f"Pair {pair} has a single arm; a comparison requires baseline and treated arms.")
    elif not valid_arm_shape:
        status = "INCOMPLETE"
        claim_boundary = "requires exactly one baseline and one treated arm"
        reasons.append(
            f"Pair {pair} does not contain exactly two unambiguous arms: one baseline and one treated."
        )
    elif not all(started.values()) or not all(checkpointed.values()):
        status = "INCOMPLETE"
        claim_boundary = "incomplete pair; no comparison"
        reasons.append(f"Pair {pair} did not reach the interruption checkpoint in both arms.")
    elif verdict_pending:
        status = "INCOMPLETE"
        claim_boundary = "pending pair-verdict transaction; no comparison"
        reasons.append(
            f"Pair {pair} has an uncommitted pair-verdict transaction; retry or recover it before claims."
        )
    else:
        signatures = {}
        verdict_errors = []
        lifecycle_valid = True
        for arm, events in arm_events.items():
            start, checkpoint, verdict_position = lifecycle_positions(events)
            if (
                start is None
                or checkpoint is None
                or verdict_position is None
                or verdict_position <= checkpoint
            ):
                lifecycle_valid = False
            signature, error = pair_verdict_signature(pair, str(conditions[arm]), events)
            signatures[arm] = signature
            if error:
                verdict_errors.append(f"{arm}: {error}")
        coherent = (
            verdict_committed
            and not verdict_errors
            and all(signature for signature in signatures.values())
            and len(set(signatures.values())) == 1
        )
        if lifecycle_valid and coherent:
            status = "VALID COMPARISON"
            claim_boundary = "consistency evidence only; not causality"
            reasons.append(
                f"Pair {pair} completed one baseline and one treated arm with coherent pair-verdict events; "
                "a single internally consistent pair is consistency evidence, not causality."
            )
        else:
            status = "INCOMPLETE"
            claim_boundary = "checkpointed but no coherent pair verdict"
            if not lifecycle_valid:
                verdict_errors.append("pair-verdict must occur after arm_start and interruption_reached")
            if not coherent and not verdict_errors:
                verdict_errors.append("pair-verdict notes differ across arms")
            reasons.append(
                f"Pair {pair} has no coherent post-checkpoint verdict: {'; '.join(verdict_errors)}."
            )

    observed_counts = {arm: count for arm, count in failing_counts.items() if count is not None}
    if len(set(observed_counts.values())) > 1:
        reasons.append(
            f"Pair {pair} failing_count values differ across arms; this is an observed fact only "
            "and does not imply scope_differs without an explicit audit event."
        )

    return {
        "pair": pair,
        "status": status,
        "claim_boundary": claim_boundary,
        "scope_differs_event": scope_differs,
        "arms": tuple(arm_events),
        "started": started,
        "checkpointed": checkpointed,
        "conditions": conditions,
        "failing_counts": failing_counts,
        "resume_time": resume_time,
        "reasons": reasons,
    }


def layer_verdict(
    layer: str,
    spec: dict[str, Any],
    all_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure upstream runtime evidence classification. Mechanism evidence only —
    performance claims always additionally require valid pairs."""
    def matches_marker(name: str, marker: str) -> bool:
        return re.search(
            rf"(?:^|{LAYER_EVENT_DELIMITERS}){re.escape(marker)}(?:$|{LAYER_EVENT_DELIMITERS})",
            name,
        ) is not None

    observed_events = sorted({
        name
        for name in (str(event.get("event", "")) for event in all_events)
        # pair-checkpoint-audit is ASCS harness audit evidence, not upstream runtime evidence
        if name != "pair-checkpoint-audit"
        and any(matches_marker(name, marker) for marker in spec["event_markers"])
    })

    status = "mechanism events recorded; no validated claims" if observed_events else "no evidence"

    allowed_claims = []
    if status != "no evidence":
        allowed_claims.append(
            f"{spec['upstream']} mechanism events were recorded in this experiment (mechanism-level evidence only)."
        )
    disallowed_claims = list(spec["disallowed_without_evidence"])
    # Valid pairs are consistency evidence, never causality, so a per-layer
    # productivity claim stays disallowed regardless of pair validity.
    disallowed_claims.append(f"{spec['upstream']} improved productivity in this experiment.")

    return {
        "layer": layer,
        "upstream": spec["upstream"],
        "role": spec["role"],
        "status": status,
        "observed_events": observed_events,
        "allowed_claims": allowed_claims,
        "disallowed_claims": disallowed_claims,
        "risks": list(spec["risks"]),
        "required_evidence": list(spec["required_evidence"]),
    }


def ascs_evidence_loop_verdict(
    pair_statuses: list[dict[str, Any]],
    any_checkpoint: bool,
    any_trusted_recovery: bool,
) -> dict[str, Any]:
    """Classify ASCS helper/harness evidence separately from upstream runtime evidence."""
    if any_checkpoint and any_trusted_recovery:
        status = "checkpoint recording and event-derived recovery timing evidence"
    elif any_checkpoint:
        status = "checkpoint recording evidence; no recovery evidence"
    elif any_trusted_recovery:
        status = "event-derived recovery timing evidence; no checkpoint evidence"
    else:
        status = "no ASCS evidence-loop mechanism evidence"

    observed = []
    if any(any(entry["started"].values()) for entry in pair_statuses):
        observed.append("arm_start")
    if any_checkpoint:
        observed.append("interruption_reached")
    if any(any(resume["trusted"] for resume in entry["resume_time"].values()) for entry in pair_statuses):
        observed.extend([RESUME_START_EVENT, FIRST_PROGRESS_EVENT])
    if any(entry["scope_differs_event"] for entry in pair_statuses):
        observed.append("pair-checkpoint-audit")
    if any(str(entry["status"]).startswith("VOID") for entry in pair_statuses):
        observed.append("void-pair")

    return {
        "status": status,
        "conceptual_layers": {
            "compression": "no ASCS evidence in Experiment 004",
            "health_detection": "no ASCS evidence in Experiment 004",
            "checkpointing": "evidence present" if any_checkpoint else "no evidence",
            "recovery": "event-derived timing evidence present" if any_trusted_recovery else "no recovery evidence",
        },
        "observed_events": sorted(set(observed)),
        "allowed_claims": [
            "ASCS helper/harness recorded evidence-loop events."
        ] if observed else [],
        "disallowed_claims": [
            "ASCS evidence-loop events are compact-plus runtime evidence.",
            "ASCS evidence-loop events prove productivity, speed, model quality, or full-stack composition effects.",
        ],
    }


def composition_verdict(layer_evidence: dict[str, dict[str, Any]], valid_pair_count: int) -> dict[str, Any]:
    """Full-stack composition claims require isolated evidence for every
    layer AND valid pairs — and even then remain consistency evidence."""
    missing = [entry["upstream"] for entry in layer_evidence.values() if entry["status"] == "no evidence"]
    supported = not missing and valid_pair_count > 0

    reasons = []
    if missing:
        reasons.append("No isolated evidence for: " + ", ".join(missing) + ".")
    if valid_pair_count == 0:
        reasons.append("No valid, non-void pair exists.")

    if supported:
        status = "composition consistency evidence only; not causality"
        allowed_claims = [
            "All three layers show mechanism evidence alongside a valid pair (consistency evidence only, not causality)."
        ]
        reasons.append("Every layer has evidence and a valid pair exists; still consistency evidence, not causality.")
    else:
        status = "no composition evidence"
        allowed_claims = []

    return {
        "status": status,
        "allowed_claims": allowed_claims,
        "disallowed_claims": list(COMPOSITION_DISALLOWED_CLAIMS),
        "risks": list(COMPOSITION_RISKS),
        "required_evidence": list(COMPOSITION_REQUIRED_EVIDENCE),
        "reasons": reasons,
    }


def validate_evidence_payload(
    evidence: Any, *, allow_legacy: bool = False
) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    experiment = evidence.get("experiment", "")
    if (
        not isinstance(experiment, str)
        or not experiment
        or len(experiment) > 255
        or any(ord(char) < 32 for char in experiment)
    ):
        raise ValueError("evidence experiment must be a non-empty string")
    closeout_exists = evidence.get("closeout_exists", False)
    if not isinstance(closeout_exists, bool):
        raise ValueError("evidence closeout_exists must be boolean")
    pairs = evidence.get("pairs", [])
    if not isinstance(pairs, list):
        raise ValueError("evidence pairs must be an array")
    if len(pairs) > 1000:
        raise ValueError("evidence contains too many pairs")

    normalized_pairs = []
    legacy_event_count = 0
    seen_pairs = set()
    for pair_index, entry in enumerate(pairs):
        if not isinstance(entry, dict):
            raise ValueError(f"pairs[{pair_index}] must be an object")
        pair = entry.get("pair")
        if not isinstance(pair, str) or not EVENT_ID_RE.fullmatch(pair):
            raise ValueError(f"pairs[{pair_index}].pair must be a safe identifier")
        if pair in seen_pairs:
            raise ValueError(f"duplicate pair identifier: {pair}")
        seen_pairs.add(pair)
        arm_events = entry.get("arm_events")
        if not isinstance(arm_events, dict) or not arm_events:
            raise ValueError(f"pairs[{pair_index}].arm_events must be a non-empty object")
        if len(arm_events) > 100:
            raise ValueError(f"pairs[{pair_index}] contains too many arms")
        normalized_arms = {}
        for arm, events in arm_events.items():
            if (
                not isinstance(arm, str)
                or not arm
                or len(arm) > 255
                or arm in {".", ".."}
                or any(ord(char) < 32 for char in arm)
            ):
                raise ValueError(f"pairs[{pair_index}] has an invalid arm name")
            if not isinstance(events, list):
                raise ValueError(f"pairs[{pair_index}].arm_events[{arm!r}] must be an array")
            if len(events) > 100000:
                raise ValueError(f"pairs[{pair_index}].arm_events[{arm!r}] has too many events")
            normalized_events = []
            for event_index, event in enumerate(events):
                normalized = validate_event_record(
                    event,
                    allow_legacy=allow_legacy,
                    context=f"pairs[{pair_index}].arm_events[{arm!r}][{event_index}]",
                )
                if "schema_version" not in normalized:
                    legacy_event_count += 1
                normalized_events.append(normalized)
            normalized_arms[arm] = normalized_events
        normalized_pairs.append({"pair": pair, "arm_events": normalized_arms})
    return {
        "experiment": experiment,
        "closeout_exists": closeout_exists,
        "pairs": normalized_pairs,
        "legacy_event_count": legacy_event_count,
    }


def compute_claim_verdict(
    evidence: dict[str, Any], *, allow_legacy: bool = False
) -> dict[str, Any]:
    """Pure claim-boundary verdict over parsed experiment evidence.

    Takes only in-memory data and performs no I/O. `evidence` shape:

        {
          "experiment": "004",
          "closeout_exists": bool,
          "pairs": [{"pair": "1", "arm_events": {arm_name: [event, ...]}}, ...],
        }
    """
    evidence = validate_evidence_payload(evidence, allow_legacy=allow_legacy)
    experiment = evidence["experiment"]
    closeout_exists = evidence["closeout_exists"]
    pairs = evidence["pairs"]
    legacy_event_count = evidence["legacy_event_count"]
    pair_statuses = [pair_verdict(entry["pair"], entry["arm_events"]) for entry in pairs]
    valid_pairs = [entry for entry in pair_statuses if entry["status"] == "VALID COMPARISON"]
    void_pairs = [entry for entry in pair_statuses if str(entry["status"]).startswith("VOID")]
    all_valid = bool(pair_statuses) and len(valid_pairs) == len(pair_statuses)

    if closeout_exists and not valid_pairs:
        experiment_status = "STOPPED / no valid comparison"
    elif all_valid:
        experiment_status = "COMPLETE / valid comparisons available"
    elif void_pairs:
        experiment_status = "STOPPED / no valid comparison"
    else:
        experiment_status = "INCOMPLETE / no valid comparison yet"

    if not valid_pairs:
        evidence_level = "evidence-loop validation only"
    else:
        evidence_level = f"consistency evidence only ({len(valid_pairs)} valid pair(s)); not causality"

    observed_facts = [
        f"Experiment {experiment} closeout is present"
        if closeout_exists
        else f"Experiment {experiment} closeout is not present"
    ]
    if legacy_event_count:
        observed_facts.append(
            f"{legacy_event_count} legacy event(s) were accepted through explicit compatibility mode."
        )
    for entry in pair_statuses:
        observed_facts.append(f"Pair {entry['pair']} status: {entry['status']}")
        observed_counts = {arm: count for arm, count in entry["failing_counts"].items() if count is not None}
        if observed_counts:
            rendered = ", ".join(f"{arm}={count}" for arm, count in observed_counts.items())
            observed_facts.append(
                f"Pair {entry['pair']} failing_count observed: {rendered} "
                "(observed fact only; not scope or performance evidence)"
            )
        for arm, resume in entry["resume_time"].items():
            if resume["trusted"]:
                observed_facts.append(
                    f"{arm} resume_time_seconds={resume['seconds']} (event-derived: {resume['detail']})"
                )

    allowed_claims = [f"Experiment {experiment} validated parts of the ASCS evidence loop."]
    if void_pairs:
        allowed_claims.append("ASCS can restrict claims when a pair becomes invalid.")
    allowed_claims.append(f"Experiment {experiment} produced operational lessons for future experiment design.")
    for entry in valid_pairs:
        allowed_claims.append(
            f"Pair {entry['pair']} produced an internally consistent comparison "
            "(consistency evidence only, not causality)."
        )
    # Metrics may support claims only when event-derived; untrusted values never do.
    for entry in pair_statuses:
        for arm, resume in entry["resume_time"].items():
            if resume["trusted"]:
                allowed_claims.append(
                    f"{arm} resume_time_seconds={resume['seconds']} is event-derived and reportable as an observed value."
                )

    disallowed_claims = [
        "ASCS improved productivity.",
        "Treated outperformed baseline.",
        "Baseline outperformed treated.",
        "Fable 5 is better or worse for this workflow.",
        "Auto mode speed differences prove anything about ASCS.",
    ]
    if not all_valid:
        disallowed_claims.append(f"Experiment {experiment} provides a valid counterbalanced result.")
    disallowed_claims.append("Any speed, model superiority, runtime superiority, or production-readiness claim.")
    if valid_pairs:
        disallowed_claims.append("An internally consistent pair proves causality or productivity impact.")

    any_checkpoint = any(any(entry["checkpointed"].values()) for entry in pair_statuses)
    any_trusted_recovery = any(
        resume["trusted"] for entry in pair_statuses for resume in entry["resume_time"].values()
    )
    all_events = [event for entry in pairs for events in entry["arm_events"].values() for event in events]
    layer_evidence = {
        layer: layer_verdict(layer, spec, all_events)
        for layer, spec in CLAIM_LAYERS.items()
    }
    ascs_evidence_loop = ascs_evidence_loop_verdict(pair_statuses, any_checkpoint, any_trusted_recovery)
    composition_evidence = composition_verdict(layer_evidence, len(valid_pairs))

    unsupported_claims: list[str] = []
    for claim in (
        disallowed_claims
        + ascs_evidence_loop["disallowed_claims"]
        + [claim for entry in layer_evidence.values() for claim in entry["disallowed_claims"]]
        + composition_evidence["disallowed_claims"]
    ):
        if claim not in unsupported_claims:
            unsupported_claims.append(claim)

    next_required_evidence = []
    if not valid_pairs:
        next_required_evidence.append(
            "Run a new pre-registered experiment with standardized model, effort, approval mode, and runtime conditions."
        )
        next_required_evidence.append(
            "Use valid, non-void baseline and treated arms before making treated-vs-baseline claims."
        )
    if experiment == "004":
        next_required_evidence.append("Cut the next attempt as Experiment 005 using Opus as the standard runtime.")
    for item in COMPOSITION_REQUIRED_EVIDENCE:
        if item not in next_required_evidence:
            next_required_evidence.append(item)

    reasons = []
    if closeout_exists:
        reasons.append(
            f"Experiment {experiment} closeout document is present; the experiment is treated as stopped "
            "and claim boundaries follow the closeout."
        )
    for entry in pair_statuses:
        reasons.extend(entry["reasons"])
    if not valid_pairs:
        reasons.append("No valid pair remains, so evidence is limited to evidence-loop validation.")
    else:
        reasons.append(
            "Valid pairs are internal consistency evidence only; causality requires replication "
            "under a pre-registered design."
        )

    blockers = []
    if not valid_pairs:
        blockers.append("No valid, non-void pair exists; treated-vs-baseline claims are blocked.")
    if not any_trusted_recovery:
        blockers.append(
            f"No resume_time_seconds derived from `{RESUME_START_EVENT}`/`{FIRST_PROGRESS_EVENT}` events; "
            "recovery timing claims are blocked."
        )
    for entry in layer_evidence.values():
        if entry["status"] == "no evidence":
            blockers.append(f"No isolated evidence for the {entry['layer']} layer ({entry['upstream']}).")
    if composition_evidence["status"] == "no composition evidence":
        blockers.append("Full-stack composition effect is unmeasured; composition claims are blocked.")

    return {
        "experiment": experiment,
        "legacy_event_count": legacy_event_count,
        "experiment_status": experiment_status,
        "pair_statuses": pair_statuses,
        "evidence_level": evidence_level,
        "observed_facts": observed_facts,
        "allowed_claims": allowed_claims,
        "disallowed_claims": disallowed_claims,
        "next_required_evidence": next_required_evidence,
        "reasons": reasons,
        "blockers": blockers,
        "ascs_evidence_loop": ascs_evidence_loop,
        "layer_evidence": layer_evidence,
        "composition_evidence": composition_evidence,
        "unsupported_claims": unsupported_claims,
    }


def experiment_004_evidence(experiments_dir: Path) -> dict[str, Any]:
    """Read-only evidence collection for Experiment 004 (the I/O layer)."""
    return {
        "experiment": "004",
        "closeout_exists": (experiments_dir / EXPERIMENT_004_CLOSEOUT).exists(),
        "pairs": [
            {
                "pair": pair,
                "arm_events": {
                    arm_dir: read_events(
                        experiments_dir / arm_dir / "events.jsonl", allow_legacy=True
                    )
                    for arm_dir in arm_dirs
                },
            }
            for pair, arm_dirs in EXPERIMENT_004_PAIRS.items()
        ],
    }


def experiment_004_measurement(experiments_dir: Path) -> dict[str, Any]:
    return compute_claim_verdict(experiment_004_evidence(experiments_dir), allow_legacy=True)


PAIR_TOKEN_RE = re.compile(r"(?:^|-)p(\d+)(?:-|$)")


def generic_experiment_evidence(experiment_dir: Path) -> dict[str, Any]:
    """Read-only evidence collection for any experiment directory.

    Arms are the experiment directory itself and/or its immediate
    subdirectories that contain an `events.jsonl`. Arm names containing a
    `p<N>` token (e.g. `...-p1-baseline`) are grouped into pair N; every
    other arm forms its own single-arm pair. A single-arm pair can never
    reach VALID COMPARISON, so this stays conservative by construction.
    """
    arms: dict[str, Path] = {}
    if (experiment_dir / "events.jsonl").exists():
        arms[experiment_dir.name] = experiment_dir
    if experiment_dir.is_dir():
        for child in sorted(experiment_dir.iterdir()):
            if child.is_dir() and (child / "events.jsonl").exists():
                arms[child.name] = child

    grouped: dict[str, list[str]] = {}
    for arm_name in arms:
        match = PAIR_TOKEN_RE.search(arm_name)
        pair_id = match.group(1) if match else arm_name
        grouped.setdefault(pair_id, []).append(arm_name)

    def pair_sort_key(pair_id: str) -> tuple[int, str]:
        return (0, pair_id.zfill(8)) if pair_id.isdigit() else (1, pair_id)

    return {
        "experiment": experiment_dir.name,
        "closeout_exists": any(experiment_dir.glob("*closeout*.md")),
        "pairs": [
            {
                "pair": pair_id,
                "arm_events": {
                    arm_name: read_events(
                        arms[arm_name] / "events.jsonl", allow_legacy=True
                    )
                    for arm_name in sorted(grouped[pair_id])
                },
            }
            for pair_id in sorted(grouped, key=pair_sort_key)
        ],
    }


def generic_experiment_measurement(experiment_dir: Path) -> dict[str, Any]:
    return compute_claim_verdict(generic_experiment_evidence(experiment_dir), allow_legacy=True)


def render_measurement_text(result: dict[str, Any]) -> str:
    lines = ["ASCS MEASURE RESULT"]
    lines.append(f"- Experiment status: {result['experiment_status']}")
    lines.append("- Pair statuses:")
    for pair in result["pair_statuses"]:
        lines.append(f"  - Pair {pair['pair']}: {pair['status']} ({pair['claim_boundary']})")
    lines.append(f"- Evidence level: {result['evidence_level']}")
    for heading, key in (
        ("Observed facts", "observed_facts"),
        ("Allowed claims", "allowed_claims"),
        ("Disallowed claims", "disallowed_claims"),
        ("Next required evidence", "next_required_evidence"),
        ("Reasons", "reasons"),
        ("Blockers", "blockers"),
    ):
        lines.append(f"- {heading}:")
        for item in result[key]:
            lines.append(f"  - {item}")
    ascs_loop = result["ascs_evidence_loop"]
    lines.append(f"- ASCS evidence-loop: {ascs_loop['status']}")
    lines.append("- ASCS conceptual layers:")
    for layer, status in ascs_loop["conceptual_layers"].items():
        lines.append(f"  - {layer}: {status}")
    lines.append("- Layer evidence:")
    for layer in result["layer_evidence"].values():
        lines.append(f"  - {layer['layer']} ({layer['upstream']}): {layer['status']}")
    composition = result["composition_evidence"]
    lines.append(f"- Composition evidence: {composition['status']}")
    lines.append("- Unsupported claims:")
    for claim in result["unsupported_claims"]:
        lines.append(f"  - {claim}")
    return "\n".join(lines) + "\n"


def render_measurement_markdown(result: dict[str, Any]) -> str:
    experiment = result.get("experiment", "")
    lines = [
        f"# ASCS Claim-Boundary Report — Experiment {experiment}".rstrip(),
        "",
        f"- **Experiment status**: {result['experiment_status']}",
        f"- **Evidence level**: {result['evidence_level']}",
        "",
        "## Pair statuses",
        "",
        "| Pair | Status | Claim boundary |",
        "| --- | --- | --- |",
    ]
    for pair in result["pair_statuses"]:
        lines.append(f"| {pair['pair']} | {pair['status']} | {pair['claim_boundary']} |")
    for heading, key in (
        ("Observed facts", "observed_facts"),
        ("Allowed claims", "allowed_claims"),
        ("Disallowed claims", "disallowed_claims"),
        ("Reasons", "reasons"),
        ("Blockers", "blockers"),
        ("Next required evidence", "next_required_evidence"),
    ):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {item}" for item in result[key])
    ascs_loop = result["ascs_evidence_loop"]
    lines.extend(["", "## ASCS evidence-loop", "", f"- **Status**: {ascs_loop['status']}"])
    if ascs_loop["observed_events"]:
        lines.append(f"- **Observed events**: {', '.join(ascs_loop['observed_events'])}")
    lines.append("- **Conceptual layers**:")
    for layer, status in ascs_loop["conceptual_layers"].items():
        lines.append(f"  - {layer}: {status}")
    lines.extend(["", "## Layer evidence", ""])
    for layer in result["layer_evidence"].values():
        lines.append(f"### {layer['layer']} — {layer['upstream']}")
        lines.append("")
        lines.append(f"- **Status**: {layer['status']}")
        lines.append(f"- **Role**: {layer['role']}")
        if layer["observed_events"]:
            lines.append(f"- **Observed events**: {', '.join(layer['observed_events'])}")
        for label, key in (
            ("Allowed claims", "allowed_claims"),
            ("Disallowed claims", "disallowed_claims"),
            ("Risks", "risks"),
            ("Required evidence", "required_evidence"),
        ):
            if layer[key]:
                lines.append(f"- **{label}**:")
                lines.extend(f"  - {item}" for item in layer[key])
        lines.append("")
    composition = result["composition_evidence"]
    lines.extend(["## Composition evidence", "", f"- **Status**: {composition['status']}"])
    for label, key in (
        ("Allowed claims", "allowed_claims"),
        ("Disallowed claims", "disallowed_claims"),
        ("Risks", "risks"),
        ("Required evidence", "required_evidence"),
        ("Reasons", "reasons"),
    ):
        if composition[key]:
            lines.append(f"- **{label}**:")
            lines.extend(f"  - {item}" for item in composition[key])
    lines.extend(["", "## Unsupported claims", ""])
    lines.extend(f"- {claim}" for claim in result["unsupported_claims"])
    return "\n".join(lines) + "\n"


def print_measurement(result: dict[str, Any]) -> None:
    print(render_measurement_text(result), end="")


def output_path_rejection_reason(output_path: Path, experiments_dir: Path) -> str | None:
    if output_path.name in PROTECTED_EVIDENCE_FILENAMES:
        return f"refusing to write measure output to protected evidence filename: {output_path.name}"

    repo_experiments = (repo_root() / "experiments").resolve()
    candidate = output_path.resolve(strict=False)
    protected_roots = {experiments_dir.resolve(strict=False), repo_experiments}
    for protected_root in protected_roots:
        if candidate == protected_root or protected_root in candidate.parents:
            return f"refusing to write measure output under protected experiments directory: {protected_root}"
    return None


def measure_experiment(args: argparse.Namespace) -> int:
    experiment_dir = getattr(args, "experiment_dir", None)
    if bool(experiment_dir) == bool(args.experiment):
        print("FAIL pass exactly one of --experiment or --experiment-dir", file=sys.stderr)
        return 1
    try:
        if experiment_dir:
            experiments_dir = Path(experiment_dir)
            if not experiments_dir.is_dir():
                print(f"FAIL {experiments_dir} is not a directory", file=sys.stderr)
                return 1
            result = generic_experiment_measurement(experiments_dir)
            if not result["pair_statuses"]:
                print(
                    f"FAIL no events.jsonl found in {experiments_dir} or its immediate subdirectories",
                    file=sys.stderr,
                )
                return 1
        else:
            experiments_dir = Path(args.experiments_dir)
            result = experiment_004_measurement(experiments_dir)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL invalid evidence: {exc}", file=sys.stderr)
        return 1
    output_format = getattr(args, "format", "text")
    rendered = (
        render_measurement_markdown(result) if output_format == "markdown" else render_measurement_text(result)
    )
    output_path = getattr(args, "output", None)
    if output_path:
        # The only write `measure` ever performs: the explicitly requested
        # report path. Evidence files (events.jsonl, report.md,
        # experiment.json) and target repos are never written.
        destination = Path(output_path)
        rejection = output_path_rejection_reason(destination, experiments_dir)
        if rejection:
            print(f"FAIL {rejection}", file=sys.stderr)
            return 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
        print(f"OK wrote {destination}")
    else:
        print(rendered, end="")
    return 0


def finish_experiment(args: argparse.Namespace) -> int:
    experiment_dir = Path(args.experiment)
    experiment_json = experiment_dir / "experiment.json"
    if not experiment_json.exists():
        print(f"FAIL {experiment_json} does not exist", file=sys.stderr)
        return 1

    for field in (
        "resume_time",
        "missed_checkpoint_items",
        "repeated_failures",
        "rejected_option_relapses",
        "human_corrections",
        "recovery_quality",
    ):
        value = getattr(args, field, None)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            print(f"FAIL {field} must be a non-negative integer", file=sys.stderr)
            return 1
    if args.recovery_quality is not None and args.recovery_quality > 4:
        print("FAIL recovery_quality must be between 0 and 4", file=sys.stderr)
        return 1
    if args.missed_state_files != "n/a" and (
        isinstance(args.missed_state_files, bool)
        or not isinstance(args.missed_state_files, int)
        or args.missed_state_files < 0
    ):
        print("FAIL missed_state_files must be a non-negative integer or n/a", file=sys.stderr)
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
            "FAIL --missed-state-files n/a is only valid with --gate-profile "
            "experiment-004 or experiment-005",
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
    if gate_profile in REPORTED_ONLY_GATE_PROFILES and (
        args.missed_checkpoint_items is None or args.recovery_quality is None
    ):
        print(
            "FAIL --missed-checkpoint-items and --recovery-quality are required "
            f"with --gate-profile {gate_profile}",
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
        if gate_profile in REPORTED_ONLY_GATE_PROFILES
        else METRIC_KEYS
    )
    missing = [key for key in required_keys if key not in metrics]
    if missing:
        print(f"FAIL missing metrics: {', '.join(missing)}", file=sys.stderr)
        return 1

    typed_metrics: dict[str, Any] = {}
    try:
        for key in required_keys:
            if key == "missed_state_files" and metrics[key] == "n/a":
                typed_metrics[key] = "n/a"
            else:
                typed_metrics[key] = metric_as_int(metrics, key)
        if "recovery_quality" in metrics:
            recovery_quality = metric_as_int(metrics, "recovery_quality")
            if recovery_quality > 4:
                raise ValueError("recovery_quality must be between 0 and 4")
    except (TypeError, ValueError) as exc:
        print(f"FAIL invalid metrics: {exc}", file=sys.stderr)
        return 1
    existing_score = data.get("score", {})
    existing_scored_at = existing_score.get("scored_at") if isinstance(existing_score, dict) else None
    score = calculate_score(typed_metrics, existing_scored_at, gate_profile)

    print("| Metric | Value | Criterion |")
    print("|---|---:|---|")
    if gate_profile in REPORTED_ONLY_GATE_PROFILES:
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
    if "recovery_quality" in metrics and gate_profile not in REPORTED_ONLY_GATE_PROFILES:
        print(f"| recovery_quality | {recovery_quality} | reported only (0-4) |")
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
    init_parser.add_argument("--name", required=True, type=safe_experiment_name)
    init_parser.add_argument("--runtime", required=True, choices=("codex", "claude-code"))
    init_parser.add_argument("--target-repo", required=True)
    init_parser.add_argument("--gate-profile", choices=GATE_PROFILES, default=GATE_PROFILE_DEFAULT)
    init_parser.set_defaults(func=init_experiment)

    record_parser = subparsers.add_parser("record", help="append an event to events.jsonl")
    record_parser.add_argument("--experiment", required=True)
    record_parser.add_argument("--event", required=True)
    record_parser.add_argument("--note", required=True)
    record_parser.add_argument("--pair-id", default=None)
    record_parser.add_argument("--condition", choices=("baseline", "treated"), default=None)
    record_parser.add_argument("--transaction-id", default=None)
    record_parser.set_defaults(func=record_event)

    finish_parser = subparsers.add_parser("finish", help="save final metrics and update report.md")
    finish_parser.add_argument("--experiment", required=True)
    finish_parser.add_argument(
        "--resume-time",
        type=nonnegative_int,
        default=None,
        dest="resume_time",
        help="cross-check only; resume_time_seconds is derived from "
        "resume-start/first-progress-edit events when they exist",
    )
    finish_parser.add_argument("--gate-profile", choices=GATE_PROFILES, default=GATE_PROFILE_DEFAULT)
    finish_parser.add_argument("--missed-checkpoint-items", type=nonnegative_int, default=None)
    finish_parser.add_argument("--missed-state-files", required=True, type=parse_count_or_na)
    finish_parser.add_argument("--repeated-failures", type=nonnegative_int, default=None)
    finish_parser.add_argument("--rejected-option-relapses", type=nonnegative_int, default=None)
    finish_parser.add_argument("--human-corrections", required=True, type=nonnegative_int)
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

    measure_parser = subparsers.add_parser("measure", help="read-only claim-boundary measurement")
    measure_parser.add_argument("--experiment", choices=("004",))
    measure_parser.add_argument(
        "--experiment-dir",
        help="measure any experiment directory: arms are the directory itself and/or "
        "immediate subdirectories containing events.jsonl; p<N> name tokens group arms into pairs",
    )
    measure_parser.add_argument(
        "--experiments-dir",
        default=str(repo_root() / "experiments"),
        help="directory containing experiment evidence; defaults to this repo's experiments/",
    )
    measure_parser.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="report format (default: text)",
    )
    measure_parser.add_argument(
        "--output",
        default=None,
        help="write the report to this path instead of stdout; evidence files are never written",
    )
    measure_parser.set_defaults(func=measure_experiment)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
