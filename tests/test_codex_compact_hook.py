import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "examples" / "codex" / ".codex" / "hooks" / "ascs_compact.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location("ascs_codex_compact_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCodexCompactHook(unittest.TestCase):
    def setUp(self):
        self.hook = load_hook_module()
        self.now = datetime(2026, 7, 16, 1, 30, tzinfo=timezone.utc)

    def test_pre_post_and_compact_session_start_form_one_shot_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            state = repo / ".agent-session" / "state"
            state.mkdir(parents=True)
            (repo / ".agent-session" / "handoff.md").write_text("handoff", encoding="utf-8")
            (state / "checkpoint.md").write_text("checkpoint", encoding="utf-8")

            pre = self.hook.handle_event(
                {
                    "hook_event_name": "PreCompact",
                    "session_id": "session-1",
                    "turn_id": "turn-1",
                    "cwd": str(repo),
                    "trigger": "manual",
                    "transcript_path": "/private/sensitive/transcript.jsonl",
                },
                now=self.now,
            )
            self.assertEqual(pre, {"continue": True})

            receipts = list((repo / ".agent-session" / "hook-events").glob("compact-*.json"))
            self.assertEqual(len(receipts), 1)
            receipt_path = receipts[0]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["phase"], "pre_compact")
            self.assertEqual(receipt["trigger"], "manual")
            self.assertTrue(receipt["transcript_available"])
            self.assertNotIn("transcript_path", receipt)
            self.assertNotIn("session_id", receipt)
            self.assertNotIn("turn_id", receipt)
            self.assertEqual(receipt["state_files_present"], ["handoff.md", "state/checkpoint.md"])

            post = self.hook.handle_event(
                {
                    "hook_event_name": "PostCompact",
                    "session_id": "session-1",
                    "turn_id": "turn-1",
                    "cwd": str(repo),
                    "trigger": "manual",
                },
                now=self.now,
            )
            self.assertEqual(post, {"continue": True})

            start_payload = {
                "hook_event_name": "SessionStart",
                "source": "compact",
                "session_id": "session-1",
                "cwd": str(repo),
            }
            first = self.hook.handle_event(start_payload, now=self.now)
            context = first["hookSpecificOutput"]["additionalContext"]
            self.assertIn("untrusted recovery context", context)
            self.assertIn("scripts/check_state.py", context)
            self.assertNotIn("handoff", context.lower().split("read", 1)[0])

            second = self.hook.handle_event(start_payload, now=self.now)
            self.assertEqual(second, {"continue": True})

    def test_session_mismatch_does_not_inject_recovery_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / ".agent-session").mkdir()
            self.hook.handle_event(
                {
                    "hook_event_name": "PreCompact",
                    "session_id": "session-1",
                    "cwd": str(repo),
                    "trigger": "auto",
                },
                now=self.now,
            )
            result = self.hook.handle_event(
                {
                    "hook_event_name": "SessionStart",
                    "source": "compact",
                    "session_id": "session-2",
                    "cwd": str(repo),
                },
                now=self.now,
            )
            self.assertEqual(result, {"continue": True})

    def test_unsafe_or_malformed_input_fails_open_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            result = self.hook.handle_event(
                {
                    "hook_event_name": "PreCompact",
                    "session_id": "../escape",
                    "cwd": str(repo),
                },
                now=self.now,
            )
            self.assertEqual(result, {"continue": True})
            self.assertFalse((repo / ".agent-session").exists())

    def test_non_compact_session_start_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            result = self.hook.handle_event(
                {
                    "hook_event_name": "SessionStart",
                    "source": "resume",
                    "session_id": "session-1",
                    "cwd": tmp,
                },
                now=self.now,
            )
            self.assertEqual(result, {"continue": True})

    def test_parallel_sessions_keep_independent_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / ".agent-session").mkdir()
            for session_id in ("session-1", "session-2"):
                self.hook.handle_event(
                    {
                        "hook_event_name": "PreCompact",
                        "session_id": session_id,
                        "cwd": str(repo),
                        "trigger": "manual" if session_id == "session-1" else "auto",
                    },
                    now=self.now,
                )
            receipts = list((repo / ".agent-session" / "hook-events").glob("compact-*.json"))
            self.assertEqual(len(receipts), 2)
            self.assertEqual(
                {json.loads(path.read_text(encoding="utf-8"))["trigger"] for path in receipts},
                {"manual", "auto"},
            )
            for session_id in ("session-1", "session-2"):
                result = self.hook.handle_event(
                    {
                        "hook_event_name": "SessionStart",
                        "source": "compact",
                        "session_id": session_id,
                        "cwd": str(repo),
                    },
                    now=self.now,
                )
                self.assertIn("hookSpecificOutput", result)


if __name__ == "__main__":
    unittest.main()
