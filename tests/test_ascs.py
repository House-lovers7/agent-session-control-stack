import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ascs  # noqa: E402


@contextlib.contextmanager
def quiet():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def make_experiment(tmp: str, gate_profile="default") -> Path:
    path = Path(tmp) / "experiment"
    path.mkdir()
    data = {
        "created_at": "2026-07-06T00:00:00+00:00",
        "name": "unit",
        "runtime": "claude-code",
        "target_repo": "target",
        "events_file": "events.jsonl",
        "report_file": "report.md",
        "gate_profile": gate_profile,
        "metrics": {},
        "score": {},
    }
    (path / "experiment.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
    (path / "events.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-06T00:00:00+00:00",
                "event": "resume-start",
                "note": "start",
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-07-06T00:01:30+00:00",
                "event": "first-progress-edit",
                "note": "edit",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "report.md").write_text("# Experiment Report\n\n## Task Summary\n\nunit\n\n## Events\n\n", encoding="utf-8")
    return path


def write_events(path: Path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def make_exp004_fixture(tmp: str, *, void_pair=True, scope_differs=True, pair2_started=False) -> Path:
    root = Path(tmp)
    (root / ascs.EXPERIMENT_004_CLOSEOUT).write_text("closeout\n", encoding="utf-8")
    p1_baseline, p1_treated = ascs.EXPERIMENT_004_PAIRS["1"]
    p2_treated, p2_baseline = ascs.EXPERIMENT_004_PAIRS["2"]

    p1_baseline_events = [
        {"timestamp": "2026-07-06T00:00:00+00:00", "event": "preregistration", "note": "p1 baseline"},
        {"timestamp": "2026-07-06T00:01:00+00:00", "event": "arm_start", "note": "started"},
        {
            "timestamp": "2026-07-06T00:02:00+00:00",
            "event": "interruption_reached",
            "note": "interruption boundary reached; failing_count=2",
        },
    ]
    p1_treated_events = [
        {"timestamp": "2026-07-06T00:00:00+00:00", "event": "preregistration", "note": "p1 treated"},
        {"timestamp": "2026-07-06T00:01:00+00:00", "event": "arm_start", "note": "started"},
        {
            "timestamp": "2026-07-06T00:02:00+00:00",
            "event": "interruption_reached",
            "note": "interruption boundary reached; failing_count=3",
        },
    ]
    if scope_differs:
        audit = {
            "timestamp": "2026-07-06T00:03:00+00:00",
            "event": "pair-checkpoint-audit",
            "note": "pair-checkpoint-audit; pair=1; scope_differs=True; operator judged scope materially different; pair should be void condition 3",
        }
        p1_baseline_events.append(audit)
        p1_treated_events.append(audit)
    if void_pair:
        void = {
            "timestamp": "2026-07-06T00:04:00+00:00",
            "event": "void-pair",
            "note": "condition=3; note=Pair 1 checkpoint audit recorded scope_differs=True",
        }
        p1_baseline_events.append(void)
        p1_treated_events.append(void)

    write_events(root / p1_baseline / "events.jsonl", p1_baseline_events)
    write_events(root / p1_treated / "events.jsonl", p1_treated_events)

    p2_events = [
        {"timestamp": "2026-07-06T00:00:00+00:00", "event": "preregistration", "note": "p2"},
    ]
    if pair2_started:
        p2_events.append({"timestamp": "2026-07-06T00:01:00+00:00", "event": "arm_start", "note": "started"})
    write_events(root / p2_treated / "events.jsonl", p2_events)
    write_events(root / p2_baseline / "events.jsonl", p2_events[:1])

    for arm_dir in (p1_baseline, p1_treated, p2_treated, p2_baseline):
        (root / arm_dir / "report.md").write_text(f"# {arm_dir}\n", encoding="utf-8")
    return root


class TestExperiment004Profile(unittest.TestCase):
    def finish_args(self, experiment: Path, **overrides):
        defaults = {
            "experiment": str(experiment),
            "resume_time": None,
            "gate_profile": "experiment-004",
            "missed_checkpoint_items": 2,
            "missed_state_files": "n/a",
            "repeated_failures": None,
            "rejected_option_relapses": None,
            "human_corrections": 1,
            "recovery_quality": 3,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_finish_accepts_004_reported_only_metrics(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp, gate_profile="experiment-004")
            with quiet():
                status = ascs.finish_experiment(self.finish_args(experiment))
            self.assertEqual(status, 0)
            data = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(data["gate_profile"], "experiment-004")
            self.assertEqual(data["metrics"]["resume_time_seconds"], 90)
            self.assertEqual(data["metrics"]["missed_checkpoint_items"], 2)
            self.assertEqual(data["metrics"]["missed_state_files"], "n/a")
            self.assertEqual(data["score"]["status"], "REPORTED_ONLY")

    def test_generic_finish_still_regenerates_report(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp, gate_profile="experiment-004")
            report = experiment / "report.md"
            report.write_text(
                "# Experiment 004 Preregistration\n\n"
                "## Task Summary\n\nunit\n\n"
                "## Events\n\n"
                "## Frozen First Prompt\n\nmust be removed by generic finish\n\n",
                encoding="utf-8",
            )
            with quiet():
                status = ascs.finish_experiment(self.finish_args(experiment))
            self.assertEqual(status, 0)
            updated = report.read_text(encoding="utf-8")
            self.assertIn("## Task Summary", updated)
            self.assertNotIn("## Frozen First Prompt", updated)
            self.assertNotIn("must be removed by generic finish", updated)

    def test_default_profile_rejects_na_missed_state_files(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            args = self.finish_args(
                experiment,
                gate_profile="default",
                missed_state_files="n/a",
                repeated_failures=0,
                rejected_option_relapses=0,
            )
            with quiet():
                status = ascs.finish_experiment(args)
            self.assertEqual(status, 1)

    def test_default_profile_still_requires_003_metrics(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            args = self.finish_args(
                experiment,
                gate_profile="default",
                missed_state_files=0,
                repeated_failures=None,
                rejected_option_relapses=0,
            )
            with quiet():
                status = ascs.finish_experiment(args)
            self.assertEqual(status, 1)

    def test_score_003_shaped_experiment_without_gate_profile(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            data = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
            data.pop("gate_profile")
            data["metrics"] = {
                "resume_time_seconds": 90,
                "missed_state_files": 0,
                "repeated_failures": 0,
                "rejected_option_relapses": 0,
                "human_corrections": 1,
                "recovery_quality": 3,
            }
            (experiment / "experiment.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
            with quiet() as (out, _err):
                status = ascs.score_experiment(argparse.Namespace(experiment=str(experiment)))
            self.assertEqual(status, 0)
            self.assertIn("Score: **PASS**", out.getvalue())


class TestMeasureExperiment004(unittest.TestCase):
    def test_experiment_004_closeout_returns_no_valid_comparison(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            result = ascs.experiment_004_measurement(root)
        self.assertEqual(result["experiment_status"], "STOPPED / no valid comparison")
        self.assertEqual(result["evidence_level"], "evidence-loop validation only")

    def test_void_pair_event_blocks_treated_vs_baseline_claims(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            result = ascs.experiment_004_measurement(root)
        pair1 = result["pair_statuses"][0]
        self.assertEqual(pair1["status"], "VOID condition 3")
        self.assertIn("Treated outperformed baseline.", result["disallowed_claims"])
        self.assertIn("Baseline outperformed treated.", result["disallowed_claims"])

    def test_not_run_arms_are_incomplete_not_failures(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            result = ascs.experiment_004_measurement(root)
        pair2 = result["pair_statuses"][1]
        self.assertEqual(pair2["status"], "NOT RUN")
        self.assertEqual(pair2["claim_boundary"], "incomplete pair; not a failure")

    def test_failing_count_difference_alone_is_not_scope_differs(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp, void_pair=False, scope_differs=False)
            result = ascs.experiment_004_measurement(root)
        pair1 = result["pair_statuses"][0]
        self.assertEqual(pair1["status"], "INCOMPLETE")
        self.assertFalse(pair1["scope_differs_event"])

    def test_disallowed_claims_cover_productivity_speed_model_and_counterbalanced(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            result = ascs.experiment_004_measurement(root)
        claims = " ".join(result["disallowed_claims"])
        self.assertIn("productivity", claims)
        self.assertIn("speed", claims)
        self.assertIn("model superiority", claims)
        self.assertIn("counterbalanced result", claims)

    def test_measure_command_prints_expected_sections(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            with quiet() as (out, _err):
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment="004", experiments_dir=str(root))
                )
        self.assertEqual(status, 0)
        output = out.getvalue()
        self.assertIn("ASCS MEASURE RESULT", output)
        self.assertIn("Experiment status: STOPPED / no valid comparison", output)
        self.assertIn("Pair 1: VOID condition 3", output)
        self.assertIn("Pair 2: NOT RUN", output)
        self.assertIn("Allowed claims:", output)
        self.assertIn("Disallowed claims:", output)
        self.assertIn("Next required evidence:", output)

    def test_measure_command_is_read_only_for_events_and_reports(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            before = {
                path: path.read_text(encoding="utf-8")
                for path in root.rglob("*")
                if path.name in {"events.jsonl", "report.md"}
            }
            with quiet():
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment="004", experiments_dir=str(root))
                )
            after = {
                path: path.read_text(encoding="utf-8")
                for path in root.rglob("*")
                if path.name in {"events.jsonl", "report.md"}
            }
        self.assertEqual(status, 0)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
