import argparse
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import exp004  # noqa: E402


@contextlib.contextmanager
def quiet():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return proc.stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class TestPromptGeneration(unittest.TestCase):
    def test_prompts_generate_without_measurement_coaching(self):
        forbidden = [
            "baseline",
            "treated",
            ".agent-session",
            "protocol",
            "recovery_quality",
            "missed_checkpoint_items",
            "first-progress-edit",
            "visible failure",
            "rejected option",
            "測定手続き",
        ]
        for name in exp004.ARMS:
            arm = exp004.arm_from_name(name)
            for phase in ("first", "resume"):
                prompt = exp004.build_prompt(arm, phase)
                self.assertIn("Experiment 004", prompt) if phase == "first" else self.assertIn("checkpoint", prompt)
                for token in forbidden:
                    self.assertNotIn(token, prompt, f"{name}/{phase} contains {token!r}")

    def test_condition_prompts_share_same_template(self):
        left = exp004.build_prompt(exp004.arm_from_name("004-p1-baseline"), "first")
        right = exp004.build_prompt(exp004.arm_from_name("004-p1-treated"), "first")
        self.assertEqual(left, right)

    def test_resume_prompt_is_minimal(self):
        prompt = exp004.build_prompt(exp004.arm_from_name("004-p2-treated"), "resume")
        self.assertIn("前回の fresh session は checkpoint で終了しました。同じタスクを完了してください。", prompt)
        self.assertIn("Done definition:", prompt)
        self.assertNotIn("Report and wait", prompt)

    def test_t_b_prompt_freezes_no_primary_key_checkpoint_constraint(self):
        prompt = exp004.build_prompt(exp004.arm_from_name("004-p2-baseline"), "first")
        self.assertIn("Splinter 0004 `no_primary_key`", prompt)
        self.assertIn("ordinary `CREATE TABLE`", prompt)
        self.assertIn("Do not exercise a CTAS-created table", prompt)


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)

    def test_baseline_rejects_agent_session(self):
        (self.repo / ".agent-session").mkdir()
        with quiet():
            status = exp004.verify_baseline_setup(self.repo)
        self.assertEqual(status, 1)

    def test_treated_setup_appends_claude_marker_and_neutral_state(self):
        (self.repo / "CLAUDE.md").write_text("# Existing\n", encoding="utf-8")
        with quiet():
            status = exp004.setup_treated(self.repo)
        self.assertEqual(status, 0)
        claude = (self.repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(claude.count(exp004.MARKER_BEGIN), 1)
        self.assertEqual(claude.count(exp004.MARKER_END), 1)
        for rel in exp004.REQUIRED_STATE_FILES:
            self.assertTrue((self.repo / ".agent-session" / rel).exists(), rel)
        current_plan = (self.repo / ".agent-session/state/current-plan.md").read_text(encoding="utf-8")
        self.assertIn("Neutral Experiment 004 scaffold", current_plan)


class TestCheckpointSignature(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init")
        (self.repo / "src").mkdir()
        (self.repo / "src/app.ts").write_text("export const x = 1;\n", encoding="utf-8")
        self.base = commit_all(self.repo, "base")
        (self.repo / "src/app.ts").write_text("export const x = 2;\n", encoding="utf-8")
        self.head = commit_all(self.repo, "slice 1")
        self.arm = exp004.arm_from_name("004-p1-baseline")

    def test_accepts_one_slice1_commit_plus_uncommitted_test_diff(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("expect(false).toBe(true);\n", encoding="utf-8")
        with mock.patch.object(exp004, "arm_start_base", return_value=self.base):
            with quiet():
                signature, status = exp004.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 0)
        self.assertIsNotNone(signature)
        self.assertEqual(signature["base"], self.base)
        self.assertIn("tests/new_rule.test.ts", signature["test_files"])

    def test_rejects_implementation_diff_at_checkpoint(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("expect(false).toBe(true);\n", encoding="utf-8")
        (self.repo / "src/app.ts").write_text("export const x = 3;\n", encoding="utf-8")
        with mock.patch.object(exp004, "arm_start_base", return_value=self.base):
            with quiet():
                _signature, status = exp004.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 1)


class TestRecordAndFinishCommands(unittest.TestCase):
    def test_record_resume_start_requires_pair_audit(self):
        with mock.patch.object(exp004, "has_event", side_effect=lambda _arm, event: event == "interruption_reached"):
            with quiet():
                status = exp004.command_record_resume_start(argparse.Namespace(arm="004-p1-baseline"))
        self.assertEqual(status, 1)

    def test_finish_arm_uses_004_gate_profile_and_does_not_score(self):
        args = argparse.Namespace(
            arm="004-p2-treated",
            missed_checkpoint_items=1,
            human_corrections=0,
            recovery_quality=4,
            missed_state_files="0",
        )
        with mock.patch.object(exp004, "run_ascs", return_value=0) as run:
            status = exp004.command_finish_arm(args)
        self.assertEqual(status, 0)
        run.assert_called_once()
        call = run.call_args[0][0]
        self.assertEqual(call[0], "finish")
        self.assertIn("--gate-profile", call)
        self.assertIn("experiment-004", call)
        self.assertNotIn("score", call)


if __name__ == "__main__":
    unittest.main()
