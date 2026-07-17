#!/usr/bin/env python3
"""Exercise the checked-in Codex compact hook without starting Codex."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "examples" / "codex" / ".codex" / "hooks" / "ascs_compact.py"
TRIGGERS = ("manual", "auto")
TRANSCRIPT_SENTINEL = "/private/ASCS_TRANSCRIPT_PATH_MUST_NOT_PERSIST.jsonl"


class SmokeFailure(RuntimeError):
    pass


def invoke_hook(payload: dict[str, object]) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise SmokeFailure("hook subprocess returned non-zero")
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeFailure("hook subprocess returned invalid JSON") from exc
    if not isinstance(output, dict):
        raise SmokeFailure("hook subprocess output must be an object")
    return output


def receipt_path(repo: Path, session_id: str) -> Path:
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    return repo / ".agent-session" / "hook-events" / f"compact-{key}.json"


def read_receipt(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeFailure("compact receipt is missing or invalid") from exc
    if not isinstance(value, dict):
        raise SmokeFailure("compact receipt must be an object")
    return value


def run_smoke() -> list[dict[str, object]]:
    if not HOOK.is_file():
        raise SmokeFailure("checked-in Codex hook is missing")

    results: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ascs-codex-compact-") as tmp:
        repo = Path(tmp)
        (repo / ".git").mkdir()
        state = repo / ".agent-session" / "state"
        state.mkdir(parents=True)
        (repo / ".agent-session" / "handoff.md").write_text(
            "synthetic handoff\n", encoding="utf-8"
        )
        (state / "checkpoint.md").write_text(
            "synthetic checkpoint\n", encoding="utf-8"
        )

        for trigger in TRIGGERS:
            session_id = f"ASCS-SENSITIVE-{trigger}-SESSION"
            common = {
                "session_id": session_id,
                "turn_id": f"turn-{trigger}",
                "cwd": str(repo),
                "trigger": trigger,
            }
            pre = invoke_hook(
                {
                    **common,
                    "hook_event_name": "PreCompact",
                    "transcript_path": TRANSCRIPT_SENTINEL,
                }
            )
            if pre != {"continue": True}:
                raise SmokeFailure(f"{trigger} PreCompact did not continue")

            path = receipt_path(repo, session_id)
            before = read_receipt(path)
            if before.get("phase") != "pre_compact" or before.get("trigger") != trigger:
                raise SmokeFailure(f"{trigger} PreCompact receipt is incomplete")

            post = invoke_hook({**common, "hook_event_name": "PostCompact"})
            if post != {"continue": True}:
                raise SmokeFailure(f"{trigger} PostCompact did not continue")
            after_post = read_receipt(path)
            if after_post.get("phase") != "post_compact":
                raise SmokeFailure(f"{trigger} PostCompact receipt is incomplete")

            start = {
                "hook_event_name": "SessionStart",
                "source": "compact",
                "session_id": session_id,
                "cwd": str(repo),
            }
            first = invoke_hook(start)
            context = first.get("hookSpecificOutput")
            if not isinstance(context, dict) or "additionalContext" not in context:
                raise SmokeFailure(f"{trigger} recovery context was not injected")
            second = invoke_hook(start)
            if second != {"continue": True}:
                raise SmokeFailure(f"{trigger} recovery context was not one-shot")

            consumed = read_receipt(path)
            receipt_text = path.read_text(encoding="utf-8")
            sensitive_values_absent = (
                session_id not in receipt_text
                and TRANSCRIPT_SENTINEL not in receipt_text
                and "transcript_path" not in consumed
                and "session_id" not in consumed
                and "turn_id" not in consumed
            )
            if not sensitive_values_absent:
                raise SmokeFailure(f"{trigger} receipt persisted a sensitive value")
            if consumed.get("consumed") is not True:
                raise SmokeFailure(f"{trigger} receipt was not consumed")

            results.append(
                {
                    "trigger": trigger,
                    "receipt_consumed_once": True,
                    "sensitive_values_absent": True,
                }
            )
    return results


def main() -> int:
    try:
        result = run_smoke()
    except (OSError, SmokeFailure, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    triggers = "/".join(str(item["trigger"]) for item in result)
    print(
        "PASS: Codex compact hook {} JSON subprocess contracts, one-shot "
        "recovery, and sensitive-value non-persistence".format(triggers)
    )
    print("BOUNDARY: no Codex/model/API execution; runtime dispatch remains unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
