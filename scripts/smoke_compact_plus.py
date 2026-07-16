#!/usr/bin/env python3
"""No-model synthetic smoke for compact-plus recovery hook contracts.

This does not run Claude, PreCompact, transcript backup, or state generation.
It executes only the reviewed PostCompact marker hook and the following
UserPromptSubmit recovery hook inside isolated HOME/TMPDIR directories.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTOR_DIR = REPO_ROOT / "plugins" / "ascs" / "scripts"
sys.path.insert(0, str(DOCTOR_DIR))
import ascs_doctor as doctor  # noqa: E402


TRIGGERS = ("manual", "auto")
HOOKS_FILE_LIMIT = 256 * 1024
HOOK_OUTPUT_LIMIT = 64 * 1024
HOOK_TIMEOUT_SECONDS = 10
SUMMARY_SENTINEL = "ASCS_SMOKE_SUMMARY_MUST_NOT_BE_REINJECTED"
POST_COMMAND = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/compaction-recovery.sh"'
RECOVERY_COMMAND = (
    'bash "${CLAUDE_PLUGIN_ROOT}/hooks/'
    'userpromptsubmit-compaction-recovery.sh"'
)
REQUIRED_RECOVERY_CONTEXT = (
    "[COMPACTION RECOVERY]",
    "Treat next steps from the compaction summary as hypotheses",
    "Original memory / rule / skill files are the authoritative references",
)


class SmokeFailure(RuntimeError):
    """A sanitized, expected smoke-contract failure."""


def load_json_file(path, *, limit):
    try:
        if path.stat().st_size > limit:
            raise SmokeFailure("hook registration is too large")
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=doctor.reject_duplicate_json_keys,
        )
    except SmokeFailure:
        raise
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise SmokeFailure("hook registration is unavailable or invalid") from exc


def registered_matchers(payload, event, command):
    if not isinstance(payload, dict):
        raise SmokeFailure("hook registration root is invalid")
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        raise SmokeFailure("hook registration map is invalid")
    registrations = hooks.get(event)
    if not isinstance(registrations, list):
        raise SmokeFailure("required hook event is not registered")

    matchers = []
    for registration in registrations:
        if not isinstance(registration, dict):
            continue
        handlers = registration.get("hooks")
        if not isinstance(handlers, list):
            continue
        if any(
            isinstance(handler, dict)
            and handler.get("type") == "command"
            and handler.get("command") == command
            for handler in handlers
        ):
            matcher = registration.get("matcher", "")
            if isinstance(matcher, str):
                matchers.append(matcher)
    return tuple(matchers)


def validate_hook_registration(plugin_root):
    payload = load_json_file(
        plugin_root / "hooks" / "hooks.json", limit=HOOKS_FILE_LIMIT
    )
    post_matchers = registered_matchers(payload, "PostCompact", POST_COMMAND)
    coverage = set()
    for matcher in post_matchers:
        if matcher == "":
            coverage.update(TRIGGERS)
        elif matcher in TRIGGERS:
            coverage.add(matcher)
    if coverage != set(TRIGGERS):
        raise SmokeFailure(
            "PostCompact registration must cover manual and auto triggers"
        )

    recovery_matchers = registered_matchers(
        payload, "UserPromptSubmit", RECOVERY_COMMAND
    )
    if "" not in recovery_matchers:
        raise SmokeFailure(
            "UserPromptSubmit recovery registration is unavailable"
        )


def reviewed_content_matches(plugin_root, expected):
    if not isinstance(expected, dict):
        return False
    try:
        digest, file_count = doctor.hash_plugin_tree(plugin_root)
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return False
    return (
        digest == expected.get("digest")
        and file_count == expected.get("file_count")
    )


def hook_script(plugin_root, filename):
    root = Path(plugin_root).resolve(strict=True)
    candidate = root / "hooks" / filename
    try:
        if candidate.is_symlink():
            raise ValueError("hook script link is not trusted")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SmokeFailure("required hook script is unavailable") from exc
    if not resolved.is_file():
        raise SmokeFailure("required hook script is unavailable")
    return resolved


def isolated_environment(plugin_root, home, tmpdir):
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "TMPDIR": str(tmpdir),
        "LC_ALL": "C",
        "LANG": "C",
        "CLAUDE_PLUGIN_ROOT": str(plugin_root),
        "COMPACT_PLUS_PRIMARY_BACKEND": "",
        "COMPACT_PLUS_FALLBACK_BACKEND": "",
    }


def run_hook(script, payload, *, env, cwd, stage):
    bash = shutil.which("bash", path=env["PATH"])
    if not bash:
        raise SmokeFailure("bash is unavailable")
    try:
        result = subprocess.run(
            [bash, str(script)],
            input=json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            timeout=HOOK_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SmokeFailure(f"{stage} hook could not complete") from exc
    if result.returncode != 0:
        raise SmokeFailure(
            f"{stage} hook failed with exit code {result.returncode}"
        )
    if len(result.stdout) > HOOK_OUTPUT_LIMIT or len(result.stderr) > HOOK_OUTPUT_LIMIT:
        raise SmokeFailure(f"{stage} hook output is too large")
    if result.stderr.strip():
        raise SmokeFailure(f"{stage} hook wrote unexpected stderr")
    return result.stdout


def parse_recovery_output(raw):
    try:
        payload = json.loads(
            raw, object_pairs_hook=doctor.reject_duplicate_json_keys
        )
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SmokeFailure("recovery hook output is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"hookSpecificOutput"}:
        raise SmokeFailure("recovery hook output shape is invalid")
    specific = payload["hookSpecificOutput"]
    if not isinstance(specific, dict) or set(specific) != {
        "hookEventName",
        "additionalContext",
    }:
        raise SmokeFailure("recovery hook output shape is invalid")
    if specific.get("hookEventName") != "UserPromptSubmit":
        raise SmokeFailure("recovery hook event binding is invalid")
    context = specific.get("additionalContext")
    if not isinstance(context, str) or not context:
        raise SmokeFailure("recovery context is empty")
    for marker in REQUIRED_RECOVERY_CONTEXT:
        if marker not in context:
            raise SmokeFailure("recovery context is missing a required boundary")
    if SUMMARY_SENTINEL in context:
        raise SmokeFailure("compact summary text was reinjected")
    return context


def run_trigger_smoke(plugin_root, trigger):
    if trigger not in TRIGGERS:
        raise SmokeFailure("unsupported synthetic trigger")
    post_script = hook_script(plugin_root, "compaction-recovery.sh")
    recovery_script = hook_script(
        plugin_root, "userpromptsubmit-compaction-recovery.sh"
    )

    with TemporaryDirectory(prefix=f"ascs-compact-{trigger}-") as temporary:
        root = Path(temporary)
        home = root / "home"
        tmpdir = root / "tmp"
        work = root / "work"
        for directory in (home, tmpdir, work):
            directory.mkdir()
        transcript = work / "transcript.jsonl"
        transcript.write_text("{}\n", encoding="utf-8")
        session_id = f"ascs-smoke-{trigger}"
        env = isolated_environment(plugin_root, home, tmpdir)

        warned_dir = tmpdir / "claude-compact-warned"
        warned_dir.mkdir()
        warned_marker = warned_dir / session_id
        warned_marker.write_text("synthetic cooldown\n", encoding="utf-8")

        post_output = run_hook(
            post_script,
            {
                "session_id": session_id,
                "transcript_path": str(transcript),
                "cwd": str(work),
                "permission_mode": "default",
                "hook_event_name": "PostCompact",
                "trigger": trigger,
                "compact_summary": SUMMARY_SENTINEL,
            },
            env=env,
            cwd=work,
            stage=f"PostCompact {trigger}",
        )
        if post_output.strip():
            raise SmokeFailure("PostCompact hook wrote unexpected stdout")

        marker = tmpdir / "claude-compacted" / session_id
        if not marker.is_file():
            raise SmokeFailure("PostCompact marker was not created")
        try:
            if not marker.read_text(encoding="utf-8").strip().isdigit():
                raise SmokeFailure("PostCompact marker is malformed")
        except (OSError, UnicodeError) as exc:
            raise SmokeFailure("PostCompact marker is unreadable") from exc
        if warned_marker.exists():
            raise SmokeFailure("PostCompact cooldown marker was not cleared")

        prompt_payload = {
            "session_id": session_id,
            "transcript_path": str(transcript),
            "cwd": str(work),
            "permission_mode": "default",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "continue synthetic smoke",
        }
        recovery_output = run_hook(
            recovery_script,
            prompt_payload,
            env=env,
            cwd=work,
            stage=f"UserPromptSubmit {trigger}",
        )
        parse_recovery_output(recovery_output)
        if marker.exists():
            raise SmokeFailure("recovery marker was not consumed")

        second_output = run_hook(
            recovery_script,
            prompt_payload,
            env=env,
            cwd=work,
            stage=f"second UserPromptSubmit {trigger}",
        )
        if second_output.strip() or marker.exists():
            raise SmokeFailure("recovery injection was not one-shot")
        if any(home.rglob("*")):
            raise SmokeFailure("synthetic hook wrote into isolated HOME")

    return {
        "trigger": trigger,
        "marker_created": True,
        "marker_consumed_once": True,
        "summary_not_reinjected": True,
    }


def run_plugin_smoke(plugin_root, expected_integrity):
    root = Path(plugin_root)
    if not reviewed_content_matches(root, expected_integrity):
        raise SmokeFailure("reviewed plugin content does not match before smoke")
    validate_hook_registration(root)
    results = tuple(run_trigger_smoke(root, trigger) for trigger in TRIGGERS)
    if not reviewed_content_matches(root, expected_integrity):
        raise SmokeFailure("reviewed plugin content changed during smoke")
    return results


def discover_reviewed_compact_plus():
    reviewed = doctor.read_reviewed_plugins()
    if reviewed is None:
        raise SmokeFailure("reviewed plugin snapshot is unavailable")
    try:
        inventory = doctor.read_plugin_inventory()
        statuses = doctor.parse_plugin_statuses(inventory, reviewed)
    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise SmokeFailure("Claude plugin inventory is unavailable") from exc
    compact_status = next(
        status for status in statuses if status["name"] == "compact-plus"
    )
    if compact_status["state"] != "ENABLED":
        raise SmokeFailure(
            "compact-plus precondition is not ENABLED with reviewed content"
        )

    version = reviewed["compact-plus"]["version"]
    roots = []
    for item in inventory:
        plugin_id = item.get("id") if isinstance(item, dict) else None
        if (
            isinstance(plugin_id, str)
            and plugin_id.split("@", 1)[0] == "compact-plus"
            and item.get("enabled") is True
            and item.get("version") == version
        ):
            raw_path = item.get("installPath")
            if not isinstance(raw_path, str):
                raise SmokeFailure("reviewed compact-plus install path is unavailable")
            try:
                root = Path(raw_path).resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise SmokeFailure(
                    "reviewed compact-plus install path is unavailable"
                ) from exc
            if root not in roots:
                roots.append(root)
    if not roots:
        raise SmokeFailure("reviewed compact-plus install path is unavailable")
    return version, reviewed["compact-plus"]["content_integrity"], tuple(roots)


def main():
    try:
        version, expected_integrity, roots = discover_reviewed_compact_plus()
        for root in roots:
            run_plugin_smoke(root, expected_integrity)
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL: unexpected local smoke error (details suppressed)", file=sys.stderr)
        return 1

    print(
        "PASS: compact-plus {} reviewed content; synthetic manual/auto "
        "marker and one-shot recovery contracts".format(version)
    )
    print("BOUNDARY: no Claude/model/API/PreCompact execution; runtime dispatch remains unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
