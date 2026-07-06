import argparse
import contextlib
import io
import json
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

    def scaffold_files(self, root):
        return sorted(
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_file()
        )

    def test_treated_setup_appends_claude_marker_and_copies_frozen_scaffold(self):
        (self.repo / "CLAUDE.md").write_text("# Existing\n", encoding="utf-8")
        with quiet():
            status = exp004.setup_treated(self.repo)
        self.assertEqual(status, 0)
        claude = (self.repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(claude.count(exp004.MARKER_BEGIN), 1)
        self.assertEqual(claude.count(exp004.MARKER_END), 1)
        source = exp004.frozen_shared_scaffold_path()
        dest = self.repo / ".agent-session"
        self.assertEqual(self.scaffold_files(dest), self.scaffold_files(source))
        for rel in self.scaffold_files(source):
            self.assertEqual(
                (dest / rel).read_text(encoding="utf-8"),
                (source / rel).read_text(encoding="utf-8"),
                str(rel),
            )
        self.assertEqual(exp004.scaffold_tree_hash(source), exp004.scaffold_tree_hash(dest))

    def test_treated_setup_rejects_existing_agent_session_without_removing_it(self):
        existing = self.repo / ".agent-session/stale.md"
        existing.parent.mkdir()
        existing.write_text("stale\n", encoding="utf-8")
        with quiet() as (_out, err):
            status = exp004.setup_treated(self.repo)
        self.assertEqual(status, 1)
        self.assertIn("contamination risk", err.getvalue())
        self.assertTrue(existing.exists())
        self.assertEqual(existing.read_text(encoding="utf-8"), "stale\n")

    def test_isolation_setup_note_records_treated_scaffold_hash_evidence(self):
        with quiet():
            status = exp004.setup_treated(self.repo)
        self.assertEqual(status, 0)
        note = exp004.isolation_setup_note(
            exp004.arm_from_name("004-p1-treated"),
            self.repo,
            "a" * 40,
        )
        source_hash = exp004.scaffold_tree_hash(exp004.frozen_shared_scaffold_path())
        dest_hash = exp004.scaffold_tree_hash(self.repo / ".agent-session")
        self.assertIn(f"frozen scaffold tree sha256: {source_hash}", note)
        self.assertIn(f"copied .agent-session tree sha256: {dest_hash}", note)
        self.assertIn("scaffold hashes match: true", note)


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
    def make_finish_fixture(self, tmp: str):
        experiment = Path(tmp) / "experiment"
        experiment.mkdir()
        data = {
            "created_at": "2026-07-06T00:00:00+00:00",
            "name": "004-p1-baseline",
            "runtime": "claude-code",
            "target_repo": "supabase-rls-guard",
            "events_file": "events.jsonl",
            "report_file": "report.md",
            "gate_profile": "experiment-004",
            "metrics": {},
            "score": {},
        }
        (experiment / "experiment.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
        events = (
            json.dumps(
                {
                    "timestamp": "2026-07-06T00:00:00+00:00",
                    "event": "resume-start",
                    "note": "start",
                },
                sort_keys=True,
            )
            + "\n"
            + json.dumps(
                {
                    "timestamp": "2026-07-06T00:02:00+00:00",
                    "event": "first-progress-edit",
                    "note": "edit",
                },
                sort_keys=True,
            )
            + "\n"
        )
        report = """# Experiment 004 Preregistration - 004-p1-baseline

## Task Summary

Frozen preregistration task summary.

## Frozen First Prompt

<!-- FROZEN_FIRST_PROMPT_BEGIN -->
```text
first prompt must survive
```
<!-- FROZEN_FIRST_PROMPT_END -->

## Frozen Resume Prompt

<!-- FROZEN_RESUME_PROMPT_BEGIN -->
```text
resume prompt must survive
```
<!-- FROZEN_RESUME_PROMPT_END -->

## Metrics And Gate References

- Layer 2 pair comparison remains frozen.
- resume_time_seconds is reported only.

## Events

- Existing evidence note must survive.

## Result

<!-- Filled after the arm finishes. -->
"""
        (experiment / "events.jsonl").write_text(events, encoding="utf-8")
        (experiment / "report.md").write_text(report, encoding="utf-8")
        return experiment, report, events

    def finish_args(self):
        return argparse.Namespace(
            arm="004-p1-baseline",
            missed_checkpoint_items=1,
            human_corrections=0,
            recovery_quality=4,
            missed_state_files="n/a",
        )

    def test_record_resume_start_requires_pair_audit(self):
        with mock.patch.object(exp004, "has_event", side_effect=lambda _arm, event: event == "interruption_reached"):
            with quiet():
                status = exp004.command_record_resume_start(argparse.Namespace(arm="004-p1-baseline"))
        self.assertEqual(status, 1)

    def test_finish_arm_updates_metrics_without_rewriting_report(self):
        with TemporaryDirectory() as tmp:
            experiment, original_report, _original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp004, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp004, "events_path", return_value=experiment / "events.jsonl"):
                with quiet():
                    status = exp004.command_finish_arm(self.finish_args())
            self.assertEqual(status, 0)
            data = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(data["gate_profile"], "experiment-004")
            self.assertEqual(data["metrics"]["resume_time_seconds"], 120)
            self.assertEqual(data["metrics"]["missed_checkpoint_items"], 1)
            self.assertEqual(data["metrics"]["missed_state_files"], "n/a")
            self.assertEqual(data["score"]["status"], "REPORTED_ONLY")
            self.assertEqual((experiment / "report.md").read_text(encoding="utf-8"), original_report)

    def test_finish_arm_preserves_frozen_prompt_gate_and_evidence_sections(self):
        with TemporaryDirectory() as tmp:
            experiment, original_report, _original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp004, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp004, "events_path", return_value=experiment / "events.jsonl"):
                with quiet():
                    status = exp004.command_finish_arm(self.finish_args())
            self.assertEqual(status, 0)
            report = (experiment / "report.md").read_text(encoding="utf-8")
            for required in (
                "<!-- FROZEN_FIRST_PROMPT_BEGIN -->",
                "first prompt must survive",
                "<!-- FROZEN_RESUME_PROMPT_BEGIN -->",
                "resume prompt must survive",
                "## Metrics And Gate References",
                "Layer 2 pair comparison remains frozen.",
                "## Events",
                "Existing evidence note must survive.",
            ):
                self.assertIn(required, report)
            self.assertEqual(report, original_report)

    def test_finish_arm_leaves_events_file_unchanged(self):
        with TemporaryDirectory() as tmp:
            experiment, _original_report, original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp004, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp004, "events_path", return_value=experiment / "events.jsonl"):
                with quiet():
                    status = exp004.command_finish_arm(self.finish_args())
            self.assertEqual(status, 0)
            self.assertEqual((experiment / "events.jsonl").read_text(encoding="utf-8"), original_events)

    def test_finish_arm_does_not_call_generic_finish_or_score(self):
        with TemporaryDirectory() as tmp:
            experiment, _original_report, _original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp004, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp004, "events_path", return_value=experiment / "events.jsonl"), \
                    mock.patch.object(exp004, "run_ascs", return_value=0) as run:
                with quiet():
                    status = exp004.command_finish_arm(self.finish_args())
        self.assertEqual(status, 0)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
