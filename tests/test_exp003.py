"""Tests for scripts/exp003.py — freeze the safety boundaries before any
Experiment 003 arm runs.

Read-only against the real repository: prompt tests read the pre-registered
report.md files (never write them), setup tests run inside tempfile
directories, and every path that would record events or touch the target
repo is mocked. No test calls prepare-arm, no test invokes scripts/ascs.py.
"""

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import exp003  # noqa: E402


ALL_ARMS = [
    "003-p1-baseline",
    "003-p1-treated",
    "003-p2-treated",
    "003-p2-baseline",
    "003-p1r-baseline",
    "003-p1r-treated",
    "003-p2r-treated",
    "003-p2r-baseline",
]

# Per pair: (tokens that MUST appear in the prompt task text,
#            tokens that MUST NOT appear — the other pairs' tasks).
PAIR_TASK_TOKENS = {
    "1": (["RLS012", "materialized_view_in_api"], ["RLS014", "extension_in_public", "REVOKE"]),
    "2": (["RLS014", "foreign_table_in_api"], ["RLS012", "extension_in_public", "REVOKE"]),
    "1r": (["REVOKE", "RLS014", "foreign_table_in_api"], ["extension_in_public", "RLS012"]),
    "2r": (["ALTER POLICY", "extension_in_public", "RLS019"], ["RLS014", "RLS012", "REVOKE"]),
}

COACHING_PHRASES = [
    "visible failure を発生させる",
    "rejected option を明示する",
    "最低1回",
    "却下済み案を再提案しない",
    "発生させろ",
    "明示しろ",
]

TREATED_RESUME_READS = [
    "AGENTS.md",
    ".agent-session/handoff.md",
    "current-plan.md",
    "decision-log.md",
    "failed-attempts.md",
]

FINISH_REQUIRED_FLAGS = [
    "--missed-state-files",
    "--repeated-failures",
    "--rejected-option-relapses",
    "--human-corrections",
    "--recovery-quality",
]


@contextlib.contextmanager
def quiet():
    """Capture stdout/stderr so FAIL messages do not pollute test output."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def finish_argv(arm="003-p1-baseline", omit=None, extra=None):
    argv = ["finish-arm", arm]
    values = {
        "--missed-state-files": "0",
        "--repeated-failures": "0",
        "--rejected-option-relapses": "0",
        "--human-corrections": "0",
        "--recovery-quality": "3",
    }
    for flag, value in values.items():
        if flag == omit:
            continue
        argv += [flag, value]
    if extra:
        argv += extra
    return argv


class TestPromptGeneration(unittest.TestCase):
    def prompts(self):
        for arm_name in ALL_ARMS:
            arm = exp003.arm_from_name(arm_name)
            for phase in ("first", "resume"):
                yield arm_name, arm, phase, exp003.build_prompt(arm, phase)

    def test_all_arms_and_phases_generate(self):
        for arm_name, _arm, phase, prompt in self.prompts():
            self.assertTrue(prompt.strip(), f"{arm_name}/{phase} is empty")

    def test_task_summary_matches_pair(self):
        for arm_name, arm, phase, prompt in self.prompts():
            required, forbidden = PAIR_TASK_TOKENS[arm.pair]
            for token in required:
                self.assertIn(token, prompt, f"{arm_name}/{phase} missing {token!r}")
            for token in forbidden:
                self.assertNotIn(token, prompt, f"{arm_name}/{phase} contains {token!r}")

    def test_checkpoint_flow_matches_arm_generation(self):
        for arm_name, arm, phase, prompt in self.prompts():
            if phase != "first":
                continue
            if arm.checkpoints == 2:
                self.assertIn("checkpoint 1", prompt, f"{arm_name}/first")
                self.assertIn("checkpoint 2", prompt, f"{arm_name}/first")
                self.assertIn("Part A", prompt, f"{arm_name}/first")
            else:
                self.assertNotIn("checkpoint", prompt, f"{arm_name}/first")

    def test_condition_section_not_leaked_into_task(self):
        for arm_name, _arm, phase, prompt in self.prompts():
            self.assertNotIn("**Condition", prompt, f"{arm_name}/{phase}")

    def test_baseline_prompts_do_not_instruct_reading_state(self):
        for arm_name, arm, phase, prompt in self.prompts():
            if arm.condition != "baseline":
                continue
            self.assertNotIn(".agent-session/handoff.md", prompt, f"{arm_name}/{phase}")
            self.assertNotIn("current-plan.md", prompt, f"{arm_name}/{phase}")
            self.assertIn(".agent-session/ は", prompt, f"{arm_name}/{phase}")

    def test_treated_resume_instructs_reading_state(self):
        for arm_name, arm, phase, prompt in self.prompts():
            if arm.condition != "treated" or phase != "resume":
                continue
            for needle in TREATED_RESUME_READS:
                self.assertIn(needle, prompt, f"{arm_name}/{phase} missing {needle}")

    def test_no_coaching_phrases(self):
        for arm_name, _arm, phase, prompt in self.prompts():
            for phrase in COACHING_PHRASES:
                self.assertNotIn(phrase, prompt, f"{arm_name}/{phase} contains {phrase!r}")


class TestArmDefinitions(unittest.TestCase):
    def test_arm_definitions_are_consistent(self):
        self.assertEqual(sorted(exp003.ARMS), sorted(ALL_ARMS))
        for name, arm in exp003.ARMS.items():
            self.assertEqual(arm.name, name)
            self.assertEqual(arm.branch, f"exp-{name}")
            self.assertTrue((REPO_ROOT / arm.experiment_dir).is_dir(), arm.experiment_dir)
            self.assertIn(arm.condition, ("baseline", "treated"))
            self.assertIn(arm.checkpoints, (1, 2))
            self.assertIn(arm.task_source, exp003.ARMS)
            self.assertEqual(exp003.ARMS[arm.task_source].pair, arm.pair)

    def test_pair_first_arm_map_is_consistent(self):
        pairs = {arm.pair for arm in exp003.ARMS.values()}
        self.assertEqual(set(exp003.PAIR_FIRST_ARM), pairs)
        for pair, first_name in exp003.PAIR_FIRST_ARM.items():
            first = exp003.ARMS[first_name]
            self.assertEqual(first.pair, pair)
            orders = [a.order for a in exp003.ARMS.values() if a.pair == pair]
            self.assertEqual(first.order, min(orders))


class TestBaselineSetupVerification(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.agents = self.repo / "AGENTS.md"

    def verify(self):
        with quiet():
            return exp003.verify_baseline_setup(self.repo)

    def test_normal_agents_md_is_accepted(self):
        self.agents.write_text("# Contributor guide\n", encoding="utf-8")
        self.assertEqual(self.verify(), 0)

    def test_marker_begin_is_rejected(self):
        self.agents.write_text(f"guide\n{exp003.MARKER_BEGIN}\n", encoding="utf-8")
        self.assertEqual(self.verify(), 1)

    def test_stray_marker_end_is_rejected(self):
        self.agents.write_text(f"guide\n{exp003.MARKER_END}\n", encoding="utf-8")
        self.assertEqual(self.verify(), 1)

    def test_agent_session_dir_is_rejected(self):
        self.agents.write_text("guide\n", encoding="utf-8")
        (self.repo / ".agent-session").mkdir()
        self.assertEqual(self.verify(), 1)

    def test_agents_md_presence_is_required_not_forbidden(self):
        # baseline must NOT demand that AGENTS.md be absent: absence fails,
        # presence (without markers) passes — the repo's own guide stays.
        self.assertEqual(self.verify(), 1)
        self.agents.write_text("guide\n", encoding="utf-8")
        self.assertEqual(self.verify(), 0)


class TestTreatedSetup(unittest.TestCase):
    ORIGINAL = "# supabase-rls-guard contributor guide\n\nkeep me intact\n"

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.agents = self.repo / "AGENTS.md"
        self.agents.write_text(self.ORIGINAL, encoding="utf-8")

    def setup_treated(self):
        with quiet():
            return exp003.setup_treated(self.repo)

    def test_appends_marker_block_and_preserves_guide(self):
        self.assertEqual(self.setup_treated(), 0)
        content = self.agents.read_text(encoding="utf-8")
        self.assertTrue(content.startswith(self.ORIGINAL))
        self.assertEqual(content.count(exp003.MARKER_BEGIN), 1)
        self.assertEqual(content.count(exp003.MARKER_END), 1)
        self.assertLess(content.index(exp003.MARKER_BEGIN), content.index(exp003.MARKER_END))
        scaffold = (REPO_ROOT / "examples/codex/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(scaffold.rstrip(), content)

    def test_copies_required_state_files(self):
        self.assertEqual(self.setup_treated(), 0)
        session = self.repo / ".agent-session"
        for rel in exp003.REQUIRED_STATE_FILES:
            self.assertTrue((session / rel).exists(), f".agent-session/{rel} missing")

    def test_existing_marker_stops_without_double_append(self):
        pre = f"{self.ORIGINAL}\n{exp003.MARKER_BEGIN}\nold block\n{exp003.MARKER_END}\n"
        self.agents.write_text(pre, encoding="utf-8")
        self.assertEqual(self.setup_treated(), 1)
        self.assertEqual(self.agents.read_text(encoding="utf-8"), pre)
        self.assertFalse((self.repo / ".agent-session").exists())

    def test_existing_agent_session_stops(self):
        (self.repo / ".agent-session").mkdir()
        self.assertEqual(self.setup_treated(), 1)
        self.assertEqual(self.agents.read_text(encoding="utf-8"), self.ORIGINAL)


class TestRecordCommands(unittest.TestCase):
    def interruption_args(self, **flags):
        defaults = {
            "arm": "003-p1-baseline",
            "visible_failure_seen": True,
            "rejected_option_seen": True,
            "libpg_rule_fired": True,
        }
        defaults.update(flags)
        return argparse.Namespace(**defaults)

    def test_interruption_requires_all_three_flags(self):
        for missing in ("visible_failure_seen", "rejected_option_seen", "libpg_rule_fired"):
            with mock.patch.object(exp003, "record_event", return_value=0) as rec:
                with quiet():
                    status = exp003.command_record_interruption(
                        self.interruption_args(**{missing: False})
                    )
                self.assertEqual(status, 1, missing)
                rec.assert_not_called()

    def test_interruption_records_when_all_flags_present(self):
        with mock.patch.object(exp003, "record_event", return_value=0) as rec:
            with quiet():
                status = exp003.command_record_interruption(self.interruption_args())
        self.assertEqual(status, 0)
        rec.assert_called_once()
        arm, event_name, note = rec.call_args[0]
        self.assertEqual(arm.name, "003-p1-baseline")
        self.assertEqual(event_name, "interruption_reached")
        self.assertIn("UTC", note)

    def test_resume_start_records_before_showing_prompt(self):
        with mock.patch.object(exp003, "record_event", return_value=0) as rec, \
                mock.patch.object(exp003, "build_prompt", return_value="RESUME PROMPT") as bp:
            manager = mock.Mock()
            manager.attach_mock(rec, "record_event")
            manager.attach_mock(bp, "build_prompt")
            with quiet() as (out, _err):
                status = exp003.command_record_resume_start(
                    argparse.Namespace(arm="003-p1-treated")
                )
        self.assertEqual(status, 0)
        names = [name for name, _args, _kwargs in manager.mock_calls]
        self.assertIn("record_event", names)
        self.assertIn("build_prompt", names)
        self.assertLess(names.index("record_event"), names.index("build_prompt"))
        self.assertEqual(rec.call_args[0][1], "resume-start")
        self.assertIn("RESUME PROMPT", out.getvalue())

    def test_resume_start_failure_does_not_show_prompt(self):
        with mock.patch.object(exp003, "record_event", return_value=1) as rec, \
                mock.patch.object(exp003, "build_prompt", return_value="RESUME PROMPT") as bp:
            with quiet() as (out, _err):
                status = exp003.command_record_resume_start(
                    argparse.Namespace(arm="003-p1-treated")
                )
        self.assertEqual(status, 1)
        rec.assert_called_once()
        bp.assert_not_called()
        self.assertNotIn("RESUME PROMPT", out.getvalue())

    def test_first_progress_edit_records_expected_event(self):
        with mock.patch.object(exp003, "record_event", return_value=0) as rec:
            with quiet():
                status = exp003.command_record_first_progress_edit(
                    argparse.Namespace(arm="003-p2-baseline")
                )
        self.assertEqual(status, 0)
        rec.assert_called_once()
        arm, event_name, note = rec.call_args[0]
        self.assertEqual(arm.name, "003-p2-baseline")
        self.assertEqual(event_name, "first-progress-edit")
        self.assertIn("UTC", note)


class TestFinishArm(unittest.TestCase):
    def parse(self, argv):
        parser = exp003.build_parser()
        with quiet():
            return parser.parse_args(argv)

    def test_all_five_metrics_are_required(self):
        for omitted in FINISH_REQUIRED_FLAGS:
            with self.assertRaises(SystemExit, msg=omitted):
                self.parse(finish_argv(omit=omitted))

    def test_valid_invocation_parses(self):
        args = self.parse(finish_argv())
        self.assertEqual(args.recovery_quality, 3)

    def test_no_resume_time_argument_exists(self):
        with self.assertRaises(SystemExit):
            self.parse(finish_argv(extra=["--resume-time", "42"]))

    def test_recovery_quality_only_accepts_0_to_4(self):
        for bad in ("5", "-1"):
            with self.assertRaises(SystemExit, msg=bad):
                self.parse(finish_argv(omit="--recovery-quality",
                                       extra=["--recovery-quality", bad]))

    def finish_args(self):
        return argparse.Namespace(
            arm="003-p1-baseline",
            missed_state_files=0,
            repeated_failures=1,
            rejected_option_relapses=0,
            human_corrections=0,
            recovery_quality=3,
        )

    def test_calls_finish_then_score(self):
        with mock.patch.object(exp003, "run_ascs", return_value=0) as run:
            status = exp003.command_finish_arm(self.finish_args())
        self.assertEqual(status, 0)
        self.assertEqual(run.call_count, 2)
        finish_call = run.call_args_list[0][0][0]
        score_call = run.call_args_list[1][0][0]
        expected_dir = exp003.arm_from_name("003-p1-baseline").experiment_dir
        self.assertEqual(finish_call[0], "finish")
        self.assertIn(expected_dir, finish_call)
        self.assertIn("--recovery-quality", finish_call)
        self.assertIn("--repeated-failures", finish_call)
        self.assertEqual(finish_call[finish_call.index("--repeated-failures") + 1], "1")
        self.assertEqual(score_call[0], "score")
        self.assertIn(expected_dir, score_call)

    def test_score_is_skipped_when_finish_fails(self):
        with mock.patch.object(exp003, "run_ascs", return_value=1) as run:
            status = exp003.command_finish_arm(self.finish_args())
        self.assertEqual(status, 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args_list[0][0][0][0], "finish")


class TestStatus(unittest.TestCase):
    EVENTS = [
        {"timestamp": "2026-07-06T01:00:00+00:00", "event": "preregistration", "note": "n1"},
        {"timestamp": "2026-07-06T02:00:00+00:00", "event": "resume-start", "note": "n2"},
    ]

    def test_lists_timestamps_and_event_names_read_only(self):
        with TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            payload = "".join(json.dumps(e) + "\n" for e in self.EVENTS)
            events.write_text(payload, encoding="utf-8")
            with mock.patch.object(exp003, "events_path", return_value=events):
                with quiet() as (out, _err):
                    status = exp003.command_status(argparse.Namespace(arm="003-p1-baseline"))
            self.assertEqual(status, 0)
            lines = out.getvalue().strip().splitlines()
            self.assertEqual(
                lines,
                [
                    "2026-07-06T01:00:00+00:00\tpreregistration",
                    "2026-07-06T02:00:00+00:00\tresume-start",
                ],
            )
            self.assertEqual(events.read_text(encoding="utf-8"), payload)

    def test_missing_events_file_fails(self):
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "events.jsonl"
            with mock.patch.object(exp003, "events_path", return_value=missing):
                with quiet():
                    status = exp003.command_status(argparse.Namespace(arm="003-p1-baseline"))
            self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
