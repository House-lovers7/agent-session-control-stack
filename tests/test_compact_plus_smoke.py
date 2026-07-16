import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = REPO_ROOT / "scripts" / "smoke_compact_plus.py"


def load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_compact_plus", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


POST_SCRIPT = r'''#!/bin/bash
set -uo pipefail
[[ -z "${ANTHROPIC_API_KEY+x}" ]] || exit 91
[[ -z "${ANTHROPIC_AUTH_TOKEN+x}" ]] || exit 92
[[ -z "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]] || exit 93
[[ "${COMPACT_PLUS_PRIMARY_BACKEND+x}" == x ]] || exit 94
[[ -z "${COMPACT_PLUS_PRIMARY_BACKEND}" ]] || exit 95
[[ "${COMPACT_PLUS_FALLBACK_BACKEND+x}" == x ]] || exit 96
[[ -z "${COMPACT_PLUS_FALLBACK_BACKEND}" ]] || exit 97
INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')
[[ -n "$SESSION_ID" ]] || exit 98
mkdir -p "$TMPDIR/claude-compacted"
printf '1\n' > "$TMPDIR/claude-compacted/$SESSION_ID"
rm -f "$TMPDIR/claude-compact-warned/$SESSION_ID"
'''


RECOVERY_SCRIPT = r'''#!/bin/bash
set -uo pipefail
INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')
MARKER="$TMPDIR/claude-compacted/$SESSION_ID"
[[ -f "$MARKER" ]] || exit 0
rm -f "$MARKER"
printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"[COMPACTION RECOVERY] Context compaction occurred. Treat next steps from the compaction summary as hypotheses. Original memory / rule / skill files are the authoritative references."}}'
'''


def write_fake_plugin(root, *, post_matcher="", leak_summary=False):
    hooks_dir = root / "hooks"
    hooks_dir.mkdir(parents=True)
    post = hooks_dir / "compaction-recovery.sh"
    recovery = hooks_dir / "userpromptsubmit-compaction-recovery.sh"
    post.write_text(POST_SCRIPT, encoding="utf-8")
    recovery_text = RECOVERY_SCRIPT
    if leak_summary:
        recovery_text = recovery_text.replace(
            "Original memory / rule / skill files are the authoritative references.",
            "Original memory / rule / skill files are the authoritative references. "
            "ASCS_SMOKE_SUMMARY_MUST_NOT_BE_REINJECTED",
        )
    recovery.write_text(recovery_text, encoding="utf-8")
    hooks = {
        "hooks": {
            "PostCompact": [
                {
                    "matcher": post_matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/compaction-recovery.sh"',
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/userpromptsubmit-compaction-recovery.sh"',
                        }
                    ],
                }
            ],
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")


class TestCompactPlusSmoke(unittest.TestCase):
    def test_manual_and_auto_marker_recovery_are_one_shot_and_isolated(self):
        smoke = load_smoke()
        with TemporaryDirectory() as tmp:
            plugin_root = Path(tmp) / "compact-plus"
            write_fake_plugin(plugin_root)
            digest, file_count = smoke.doctor.hash_plugin_tree(plugin_root)

            result = smoke.run_plugin_smoke(
                plugin_root,
                {"digest": digest, "file_count": file_count},
            )

        self.assertEqual(tuple(item["trigger"] for item in result), ("manual", "auto"))
        self.assertTrue(all(item["marker_created"] for item in result))
        self.assertTrue(all(item["marker_consumed_once"] for item in result))
        self.assertTrue(all(item["summary_not_reinjected"] for item in result))

    def test_registration_must_cover_auto_as_well_as_manual(self):
        smoke = load_smoke()
        with TemporaryDirectory() as tmp:
            plugin_root = Path(tmp) / "compact-plus"
            write_fake_plugin(plugin_root, post_matcher="manual")
            digest, file_count = smoke.doctor.hash_plugin_tree(plugin_root)

            with self.assertRaisesRegex(smoke.SmokeFailure, "manual and auto"):
                smoke.run_plugin_smoke(
                    plugin_root,
                    {"digest": digest, "file_count": file_count},
                )

    def test_compact_summary_text_must_not_be_reinjected(self):
        smoke = load_smoke()
        with TemporaryDirectory() as tmp:
            plugin_root = Path(tmp) / "compact-plus"
            write_fake_plugin(plugin_root, leak_summary=True)
            digest, file_count = smoke.doctor.hash_plugin_tree(plugin_root)

            with self.assertRaisesRegex(smoke.SmokeFailure, "summary"):
                smoke.run_plugin_smoke(
                    plugin_root,
                    {"digest": digest, "file_count": file_count},
                )

    def test_content_drift_stops_before_hook_execution(self):
        smoke = load_smoke()
        with TemporaryDirectory() as tmp:
            plugin_root = Path(tmp) / "compact-plus"
            write_fake_plugin(plugin_root)
            digest, file_count = smoke.doctor.hash_plugin_tree(plugin_root)
            (plugin_root / "hooks" / "compaction-recovery.sh").write_text(
                POST_SCRIPT + "exit 99\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(smoke.SmokeFailure, "content"):
                smoke.run_plugin_smoke(
                    plugin_root,
                    {"digest": digest, "file_count": file_count},
                )


if __name__ == "__main__":
    unittest.main()
