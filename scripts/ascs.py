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
    return derive_resume_time_from_events(read_events(events_path))


def derive_resume_time_from_events(events: list[dict[str, Any]]) -> tuple[int | None, str]:
    """Pure counterpart of derive_resume_time over already-parsed events."""
    resume_start = None
    first_progress = None
    for event in events:
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


def read_events(events_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not events_path.exists():
        return events
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError(f"{events_path}:{line_number}: event must be a JSON object")
        events.append(event)
    return events


def has_event(events: list[dict[str, Any]], event_name: str) -> bool:
    return any(event.get("event") == event_name for event in events)


def event_notes(events: list[dict[str, Any]], event_name: str) -> list[str]:
    return [str(event.get("note", "")) for event in events if event.get("event") == event_name]


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


def pair_verdict(pair: str, arm_events: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pure per-pair claim-boundary classification over parsed events."""
    all_events = [event for events in arm_events.values() for event in events]
    condition = void_condition(all_events)
    scope_differs = has_scope_differs_event(all_events)
    started = {arm: has_event(events, "arm_start") for arm, events in arm_events.items()}
    checkpointed = {arm: has_event(events, "interruption_reached") for arm, events in arm_events.items()}
    failing_counts = {arm: failing_count(events) for arm, events in arm_events.items()}
    resume_time = {}
    for arm, events in arm_events.items():
        seconds, detail = derive_resume_time_from_events(events)
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
    elif not all(started.values()) or not all(checkpointed.values()):
        status = "INCOMPLETE"
        claim_boundary = "incomplete pair; no comparison"
        reasons.append(f"Pair {pair} did not reach the interruption checkpoint in both arms.")
    elif all(has_event(events, "pair-verdict") for events in arm_events.values()):
        status = "VALID COMPARISON"
        claim_boundary = "consistency evidence only; not causality"
        reasons.append(
            f"Pair {pair} completed both arms with pair-verdict events; "
            "a single internally consistent pair is consistency evidence, not causality."
        )
    else:
        status = "INCOMPLETE"
        claim_boundary = "checkpointed but no valid verdict"
        reasons.append(f"Pair {pair} reached checkpoints but recorded no pair-verdict.")

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
    observed_events = sorted({
        name
        for name in (str(event.get("event", "")) for event in all_events)
        # pair-checkpoint-audit is ASCS harness audit evidence, not upstream runtime evidence
        if name != "pair-checkpoint-audit" and any(marker in name for marker in spec["event_markers"])
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


def compute_claim_verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    """Pure claim-boundary verdict over parsed experiment evidence.

    Takes only in-memory data and performs no I/O. `evidence` shape:

        {
          "experiment": "004",
          "closeout_exists": bool,
          "pairs": [{"pair": "1", "arm_events": {arm_name: [event, ...]}}, ...],
        }
    """
    experiment = str(evidence.get("experiment", ""))
    closeout_exists = bool(evidence.get("closeout_exists"))
    pairs = evidence.get("pairs", [])
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
                    arm_dir: read_events(experiments_dir / arm_dir / "events.jsonl")
                    for arm_dir in arm_dirs
                },
            }
            for pair, arm_dirs in EXPERIMENT_004_PAIRS.items()
        ],
    }


def experiment_004_measurement(experiments_dir: Path) -> dict[str, Any]:
    return compute_claim_verdict(experiment_004_evidence(experiments_dir))


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
    experiments_dir = Path(args.experiments_dir)
    if args.experiment != "004":
        print("FAIL only Experiment 004 measurement is supported", file=sys.stderr)
        return 1
    result = experiment_004_measurement(experiments_dir)
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

    measure_parser = subparsers.add_parser("measure", help="read-only claim-boundary measurement")
    measure_parser.add_argument("--experiment", required=True, choices=("004",))
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
