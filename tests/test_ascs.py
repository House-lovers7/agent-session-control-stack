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


if __name__ == "__main__":
    unittest.main()
