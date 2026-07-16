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
    root = Path(tmp) / "experiments"
    root.mkdir()
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


def ev(name, note="", timestamp="2026-07-06T00:00:00+00:00"):
    return {"timestamp": timestamp, "event": name, "note": note}


def v1ev(name, note="recorded", timestamp="2026-07-06T00:00:00+00:00"):
    return {
        "schema_version": 1,
        "timestamp": timestamp,
        "event": name,
        "note": note,
    }


def checkpointed_arm(failing=2):
    return [
        ev("preregistration", "pre"),
        ev("arm_start", "started"),
        ev("interruption_reached", f"interruption boundary reached; failing_count={failing}"),
    ]


def valid_arm(failing=2, with_resume=False):
    events = checkpointed_arm(failing) + [ev("pair-verdict", "verdict recorded")]
    if with_resume:
        events.append(ev("resume-start", "resume", "2026-07-06T01:00:00+00:00"))
        events.append(ev("first-progress-edit", "edit", "2026-07-06T01:00:42+00:00"))
    return events


def pure_evidence(pairs, closeout=True):
    return {"experiment": "004", "closeout_exists": closeout, "pairs": pairs}


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


class TestEvidenceBoundaries(unittest.TestCase):
    def test_experiment_name_rejects_traversal_before_writing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(
                name="../escaped",
                runtime="codex",
                target_repo="target",
                gate_profile="default",
            )
            with mock.patch.object(ascs, "repo_root", return_value=root), quiet() as (_out, err):
                status = ascs.init_experiment(args)
            self.assertEqual(status, 1)
            self.assertIn("experiment name", err.getvalue())
            self.assertFalse((root / "escaped").exists())

    def test_negative_metric_is_rejected_by_cli_parser(self):
        parser = ascs.build_parser()
        with quiet(), self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "finish",
                    "--experiment",
                    "example",
                    "--missed-state-files",
                    "0",
                    "--human-corrections",
                    "-1",
                ]
            )

    def test_negative_persisted_metric_cannot_score_pass(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            data = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
            data["metrics"] = {
                "resume_time_seconds": 1,
                "missed_state_files": 0,
                "repeated_failures": 0,
                "rejected_option_relapses": 0,
                "human_corrections": -1,
            }
            (experiment / "experiment.json").write_text(json.dumps(data), encoding="utf-8")
            with quiet() as (out, err):
                status = ascs.score_experiment(argparse.Namespace(experiment=str(experiment)))
        self.assertEqual(status, 1)
        self.assertNotIn("Score: **PASS**", out.getvalue())
        self.assertIn("non-negative", err.getvalue())

    def test_reported_only_profile_also_rejects_negative_metrics(self):
        metrics = {
            "resume_time_seconds": 1,
            "missed_checkpoint_items": 0,
            "missed_state_files": "n/a",
            "human_corrections": -1,
            "recovery_quality": 3,
        }
        with self.assertRaisesRegex(ValueError, "non-negative"):
            ascs.calculate_score(metrics, gate_profile="experiment-004")

    def test_legacy_event_read_requires_explicit_opt_in(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            write_events(path, [ev("resume-start", "legacy")])
            with self.assertRaises(ValueError):
                ascs.read_events(path)
            events = ascs.read_events(path, allow_legacy=True)
        self.assertEqual(events[0]["event"], "resume-start")

    def test_unknown_event_schema_version_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            event = v1ev("resume-start")
            event["schema_version"] = 2
            write_events(path, [event])
            with self.assertRaises(ValueError):
                ascs.read_events(path)

    def test_duplicate_event_keys_fail_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                '{"schema_version":1,"timestamp":"2026-07-06T00:00:00+00:00",'
                '"event":"resume-start","event":"first-progress-edit","note":"ambiguous"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ambiguous JSON"):
                ascs.read_events(path)

    def test_record_writes_schema_version_one(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            (experiment / "events.jsonl").write_text("", encoding="utf-8")
            with quiet():
                status = ascs.record_event(
                    argparse.Namespace(
                        experiment=str(experiment), event="resume-start", note="start"
                    )
                )
            event = json.loads((experiment / "events.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(event["schema_version"], 1)

    def test_record_rejects_missing_experiment_metadata_without_appending(self):
        with TemporaryDirectory() as tmp:
            experiment = Path(tmp) / "experiment"
            experiment.mkdir()
            events_path = experiment / "events.jsonl"
            events_path.write_text("", encoding="utf-8")
            with quiet() as (_out, err):
                status = ascs.record_event(
                    argparse.Namespace(
                        experiment=str(experiment), event="resume-start", note="start"
                    )
                )
            self.assertEqual(status, 1)
            self.assertEqual(events_path.read_text(encoding="utf-8"), "")
            self.assertIn("experiment.json", err.getvalue())

    def test_record_rejects_missing_events_file_without_creating_it(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            events_path = experiment / "events.jsonl"
            events_path.unlink()
            with quiet() as (_out, err):
                status = ascs.record_event(
                    argparse.Namespace(
                        experiment=str(experiment), event="resume-start", note="start"
                    )
                )
            self.assertEqual(status, 1)
            self.assertFalse(events_path.exists())
            self.assertIn("events.jsonl", err.getvalue())

    def test_record_rejects_ambiguous_experiment_metadata_without_appending(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            events_path = experiment / "events.jsonl"
            events_path.write_text("", encoding="utf-8")
            (experiment / "experiment.json").write_text(
                '{"events_file":"other.jsonl","events_file":"events.jsonl"}\n',
                encoding="utf-8",
            )
            with quiet() as (_out, err):
                status = ascs.record_event(
                    argparse.Namespace(
                        experiment=str(experiment), event="resume-start", note="start"
                    )
                )
            self.assertEqual(status, 1)
            self.assertEqual(events_path.read_text(encoding="utf-8"), "")
            self.assertIn("invalid experiment evidence", err.getvalue())

    def test_record_rejects_malformed_existing_events_without_appending(self):
        with TemporaryDirectory() as tmp:
            experiment = make_experiment(tmp)
            events_path = experiment / "events.jsonl"
            original = "{bad-json}\n"
            events_path.write_text(original, encoding="utf-8")
            with quiet() as (_out, err):
                status = ascs.record_event(
                    argparse.Namespace(
                        experiment=str(experiment), event="resume-start", note="start"
                    )
                )
            self.assertEqual(status, 1)
            self.assertEqual(events_path.read_text(encoding="utf-8"), original)
            self.assertIn("invalid experiment evidence", err.getvalue())

    def test_malformed_evidence_fails_measure_closed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment"
            arm = root / "run-p1-baseline"
            arm.mkdir(parents=True)
            write_events(
                arm / "events.jsonl",
                [
                    {
                        "schema_version": 1,
                        "timestamp": "2026-07-06T00:00:00+00:00",
                        "event": 42,
                        "note": "bad",
                    }
                ],
            )
            with quiet() as (_out, err):
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment=None, experiment_dir=str(root), format="text")
                )
        self.assertEqual(status, 1)
        self.assertIn("invalid evidence", err.getvalue())

    def test_aborted_resume_requires_a_fresh_resume_start(self):
        seconds, detail = ascs.derive_resume_time_from_events(
            [
                v1ev("resume-start", timestamp="2026-07-06T00:00:00+00:00"),
                v1ev("resume-attempt-aborted", timestamp="2026-07-06T00:00:10+00:00"),
                v1ev("first-progress-edit", timestamp="2026-07-06T00:01:00+00:00"),
            ]
        )
        self.assertIsNone(seconds)
        self.assertIn("fresh `resume-start`", detail)

    def test_arbitrary_arm_names_cannot_form_valid_comparison(self):
        evidence = pure_evidence(
            [{"pair": "1", "arm_events": {"red": valid_arm(), "blue": valid_arm()}}],
            closeout=False,
        )
        pair = ascs.compute_claim_verdict(evidence, allow_legacy=True)["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")
        self.assertIn("baseline", pair["claim_boundary"])

    def test_more_than_two_arms_cannot_form_valid_comparison(self):
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": valid_arm(),
                        "run-p1-treated": valid_arm(),
                        "run-p1-extra": valid_arm(),
                    },
                }
            ],
            closeout=False,
        )
        pair = ascs.compute_claim_verdict(evidence, allow_legacy=True)["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")

    def test_pair_verdict_notes_must_be_coherent(self):
        baseline = valid_arm()
        treated = valid_arm()
        baseline[-1]["note"] = "pair=1; winner=baseline"
        treated[-1]["note"] = "pair=1; winner=treated"
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": baseline,
                        "run-p1-treated": treated,
                    },
                }
            ],
            closeout=False,
        )
        pair = ascs.compute_claim_verdict(evidence, allow_legacy=True)["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")
        self.assertIn("coherent", pair["claim_boundary"])

    def test_substring_event_names_do_not_count_as_layer_evidence(self):
        fake_layer_events = [
            ev("decompression", "fake"),
            ev("unhealthy", "fake"),
            ev("precompactpluspost", "fake"),
        ]
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": valid_arm() + fake_layer_events,
                        "run-p1-treated": valid_arm() + fake_layer_events,
                    },
                }
            ],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        self.assertTrue(
            all(layer["status"] == "no evidence" for layer in result["layer_evidence"].values())
        )
        self.assertEqual(result["composition_evidence"]["status"], "no composition evidence")

    def test_delimiter_bounded_layer_events_still_count(self):
        layer_events = [
            ev("pxpipe-compression", "observed"),
            ev("session-health:intervention", "observed"),
            ev("compact-plus/recovery-injection", "observed"),
        ]
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": valid_arm() + layer_events,
                        "run-p1-treated": valid_arm() + layer_events,
                    },
                }
            ],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        self.assertTrue(
            all(layer["status"] != "no evidence" for layer in result["layer_evidence"].values())
        )
        self.assertIn("consistency evidence", result["composition_evidence"]["status"])

    def test_compute_requires_explicit_legacy_mode(self):
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": valid_arm(),
                        "run-p1-treated": valid_arm(),
                    },
                }
            ],
            closeout=False,
        )
        with self.assertRaises(ValueError):
            ascs.compute_claim_verdict(evidence)


class TestComputeClaimVerdict(unittest.TestCase):
    def test_unrelated_event_does_not_license_evidence_loop_claims(self):
        evidence = {
            "experiment": "unrelated-only",
            "closeout_exists": False,
            "pairs": [
                {
                    "pair": "1",
                    "arm_events": {
                        "run": [v1ev("unrelated", "not ASCS evidence")],
                    },
                }
            ],
        }
        result = ascs.compute_claim_verdict(evidence)
        self.assertEqual(
            result["ascs_evidence_loop"]["status"],
            "no ASCS evidence-loop mechanism evidence",
        )
        self.assertEqual(result["ascs_evidence_loop"]["observed_events"], [])
        self.assertEqual(result["allowed_claims"], [])

    def test_uncommitted_pair_verdict_transaction_never_becomes_valid(self):
        transaction_id = "exp004-pair-1-verdict"
        prepare = ev(
            "pair-event-prepare",
            f"txid={transaction_id}; pair=1; target_event=pair-verdict",
        )
        verdict = ev("pair-verdict", f"winner=tie; txid={transaction_id}")
        one_commit = ev(
            "pair-event-commit",
            f"txid={transaction_id}; pair=1; target_event=pair-verdict",
        )
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": checkpointed_arm(2) + [prepare, verdict, one_commit],
                        "run-p1-treated": checkpointed_arm(2) + [prepare, verdict],
                    },
                }
            ],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")
        self.assertIn("pending pair-verdict transaction", pair["claim_boundary"])

    def test_committed_pair_verdict_transaction_is_valid(self):
        transaction_id = "exp004-pair-1-verdict"
        prepare = ev(
            "pair-event-prepare",
            f"txid={transaction_id}; pair=1; target_event=pair-verdict",
        )
        verdict = ev("pair-verdict", f"winner=tie; txid={transaction_id}")
        commit = ev(
            "pair-event-commit",
            f"txid={transaction_id}; pair=1; target_event=pair-verdict",
        )
        arm = checkpointed_arm(2) + [prepare, verdict, commit]
        evidence = pure_evidence(
            [
                {
                    "pair": "1",
                    "arm_events": {
                        "run-p1-baseline": arm,
                        "run-p1-treated": list(arm),
                    },
                }
            ],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        self.assertEqual(result["pair_statuses"][0]["status"], "VALID COMPARISON")

    def test_void_pair_blocks_treated_vs_baseline_claims(self):
        void = ev("void-pair", "condition=3; note=scope audit")
        evidence = pure_evidence([
            {"pair": "1", "arm_events": {"a": checkpointed_arm(2) + [void], "b": checkpointed_arm(3) + [void]}},
        ])
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "VOID condition 3")
        self.assertIn("Treated outperformed baseline.", result["disallowed_claims"])
        self.assertIn("Treated outperformed baseline.", result["unsupported_claims"])
        overclaims = [c for c in result["allowed_claims"] if "outperform" in c or "productivity" in c]
        self.assertEqual(overclaims, [])

    def test_not_run_pair_is_not_a_failure(self):
        evidence = pure_evidence([
            {"pair": "2", "arm_events": {"a": [ev("preregistration")], "b": [ev("preregistration")]}},
        ])
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "NOT RUN")
        self.assertEqual(pair["claim_boundary"], "incomplete pair; not a failure")
        self.assertNotIn("fail", pair["status"].lower())

    def test_failing_count_difference_is_observed_fact_only(self):
        evidence = pure_evidence(
            [{"pair": "1", "arm_events": {"a": checkpointed_arm(2), "b": checkpointed_arm(3)}}],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")
        self.assertFalse(pair["scope_differs_event"])
        fact = next(f for f in result["observed_facts"] if "failing_count observed" in f)
        self.assertIn("observed fact only", fact)

    def test_scope_differs_audit_alone_voids_pair(self):
        audit = ev("pair-checkpoint-audit", "pair=1; scope_differs=True; operator judged scope materially different")
        evidence = pure_evidence(
            [{"pair": "1", "arm_events": {"a": checkpointed_arm(2) + [audit], "b": checkpointed_arm(3)}}],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "VOID (scope_differs audit)")
        self.assertIn("no treated-vs-baseline claim", pair["claim_boundary"])

    def test_stopped_experiment_disallows_productivity_speed_model_runtime_claims(self):
        void = ev("void-pair", "condition=3; note=x")
        evidence = pure_evidence([
            {"pair": "1", "arm_events": {"a": checkpointed_arm(2) + [void], "b": checkpointed_arm(3) + [void]}},
            {"pair": "2", "arm_events": {"a": [ev("preregistration")], "b": [ev("preregistration")]}},
        ])
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        self.assertEqual(result["experiment_status"], "STOPPED / no valid comparison")
        self.assertEqual(result["evidence_level"], "evidence-loop validation only")
        joined = " ".join(result["disallowed_claims"])
        for keyword in ("productivity", "speed", "model superiority", "runtime superiority"):
            self.assertIn(keyword, joined)
        self.assertIn(
            "No valid, non-void pair exists; treated-vs-baseline claims are blocked.",
            result["blockers"],
        )

    def test_valid_pair_is_consistency_evidence_only(self):
        evidence = pure_evidence(
            [{
                "pair": "1",
                "arm_events": {
                    "run-p1-baseline": valid_arm(2),
                    "run-p1-treated": valid_arm(2),
                },
            }],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        self.assertEqual(result["experiment_status"], "COMPLETE / valid comparisons available")
        self.assertIn("consistency evidence only", result["evidence_level"])
        self.assertIn("not causality", result["evidence_level"])
        self.assertIn("ASCS improved productivity.", result["disallowed_claims"])
        self.assertIn(
            "An internally consistent pair proves causality or productivity impact.",
            result["disallowed_claims"],
        )
        self.assertEqual(result["composition_evidence"]["status"], "no composition evidence")

    def test_resume_time_trusted_only_when_event_derived(self):
        evidence = pure_evidence(
            [{
                "pair": "1",
                "arm_events": {
                    "run-p1-baseline": valid_arm(with_resume=True),
                    "run-p1-treated": valid_arm(),
                },
            }],
            closeout=False,
        )
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        resume = result["pair_statuses"][0]["resume_time"]
        self.assertTrue(resume["run-p1-baseline"]["trusted"])
        self.assertEqual(resume["run-p1-baseline"]["seconds"], 42)
        self.assertFalse(resume["run-p1-treated"]["trusted"])
        resume_claims = [c for c in result["allowed_claims"] if "resume_time_seconds" in c]
        self.assertEqual(len(resume_claims), 1)
        self.assertIn("run-p1-baseline", resume_claims[0])

    def test_layer_evidence_separates_three_layers(self):
        void = ev("void-pair", "condition=3; note=x")
        evidence = pure_evidence([
            {"pair": "1", "arm_events": {"a": checkpointed_arm(2) + [void], "b": checkpointed_arm(3) + [void]}},
        ])
        result = ascs.compute_claim_verdict(evidence, allow_legacy=True)
        layers = result["layer_evidence"]
        self.assertEqual(set(layers), {"compression", "health_detection", "checkpoint_recovery"})
        self.assertEqual(layers["compression"]["status"], "no evidence")
        self.assertEqual(layers["compression"]["allowed_claims"], [])
        self.assertEqual(layers["health_detection"]["status"], "no evidence")
        self.assertEqual(layers["checkpoint_recovery"]["status"], "no evidence")
        self.assertEqual(
            result["ascs_evidence_loop"]["status"],
            "checkpoint recording evidence; no recovery evidence",
        )
        self.assertEqual(result["composition_evidence"]["status"], "no composition evidence")
        self.assertIn("The full-stack composition effect is validated.", result["unsupported_claims"])
        self.assertIn("Token or bill reduction implies semantic correctness.", result["unsupported_claims"])
        self.assertIn(
            "ASCS evidence-loop events are compact-plus runtime evidence.",
            result["unsupported_claims"],
        )


class TestMeasureOutputFormats(unittest.TestCase):
    def test_measure_command_prints_layer_and_unsupported_sections(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            with quiet() as (out, _err):
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment="004", experiments_dir=str(root))
                )
        self.assertEqual(status, 0)
        output = out.getvalue()
        self.assertIn("- Reasons:", output)
        self.assertIn("- Blockers:", output)
        self.assertIn("- ASCS evidence-loop:", output)
        self.assertIn("checkpoint recording evidence; no recovery evidence", output)
        self.assertIn("- Layer evidence:", output)
        self.assertIn("checkpoint_recovery (compact-plus (u-ichi)): no evidence", output)
        self.assertIn("- Composition evidence: no composition evidence", output)
        self.assertIn("- Unsupported claims:", output)

    def test_measure_rejects_output_to_protected_evidence_filenames(self):
        for filename in ("events.jsonl", "report.md", "experiment.json"):
            with self.subTest(filename=filename):
                with TemporaryDirectory() as tmp:
                    root = make_exp004_fixture(tmp)
                    protected = root / "some-arm" / filename
                    protected.parent.mkdir(parents=True, exist_ok=True)
                    protected.write_text("keep me\n", encoding="utf-8")
                    with quiet() as (_out, err):
                        status = ascs.measure_experiment(
                            argparse.Namespace(
                                experiment="004",
                                experiments_dir=str(root),
                                format="markdown",
                                output=str(protected),
                            )
                        )
                    self.assertEqual(status, 1)
                    self.assertIn("protected evidence filename", err.getvalue())
                    self.assertEqual(protected.read_text(encoding="utf-8"), "keep me\n")

    def test_measure_rejects_output_under_experiments_directory(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            protected = root / "claim-boundary.md"
            with quiet() as (_out, err):
                status = ascs.measure_experiment(
                    argparse.Namespace(
                        experiment="004",
                        experiments_dir=str(root),
                        format="markdown",
                        output=str(protected),
                    )
                )
        self.assertEqual(status, 1)
        self.assertIn("protected experiments directory", err.getvalue())

    def test_measure_command_markdown_output_to_file(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            out_path = Path(tmp) / "reports" / "claim-boundary.md"
            with quiet() as (out, _err):
                status = ascs.measure_experiment(
                    argparse.Namespace(
                        experiment="004",
                        experiments_dir=str(root),
                        format="markdown",
                        output=str(out_path),
                    )
                )
            content = out_path.read_text(encoding="utf-8")
        self.assertEqual(status, 0)
        self.assertIn("OK wrote", out.getvalue())
        self.assertIn("# ASCS Claim-Boundary Report — Experiment 004", content)
        self.assertIn("| 1 | VOID condition 3 |", content)
        self.assertIn("## ASCS evidence-loop", content)
        self.assertIn("## Layer evidence", content)
        self.assertIn("## Composition evidence", content)
        self.assertIn("## Unsupported claims", content)


class TestMeasureExperimentDir(unittest.TestCase):
    def test_experiment_dir_matches_004_pair_statuses(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            legacy = ascs.experiment_004_measurement(root)
            generic = ascs.generic_experiment_measurement(root)
        legacy_pairs = {(p["pair"], p["status"]) for p in legacy["pair_statuses"]}
        generic_pairs = {(p["pair"], p["status"]) for p in generic["pair_statuses"]}
        self.assertEqual(legacy_pairs, generic_pairs)
        self.assertEqual(legacy["experiment_status"], generic["experiment_status"])

    def test_experiment_dir_single_arm_is_never_a_valid_comparison(self):
        with TemporaryDirectory() as tmp:
            arm = Path(tmp) / "2026-07-08-solo-run"
            arm.mkdir()
            write_events(arm / "events.jsonl", valid_arm())
            result = ascs.generic_experiment_measurement(arm)
        self.assertEqual(len(result["pair_statuses"]), 1)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["status"], "INCOMPLETE")
        self.assertEqual(pair["claim_boundary"], "single-arm evidence; no comparison")

    def test_experiment_dir_groups_arms_by_pair_token(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment"
            root.mkdir()
            write_events(root / "run-p1-baseline" / "events.jsonl", valid_arm(failing=2))
            write_events(root / "run-p1-treated" / "events.jsonl", valid_arm(failing=2))
            result = ascs.generic_experiment_measurement(root)
        self.assertEqual(len(result["pair_statuses"]), 1)
        pair = result["pair_statuses"][0]
        self.assertEqual(pair["pair"], "1")
        self.assertEqual(pair["status"], "VALID COMPARISON")

    def test_experiment_dir_detects_closeout_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment"
            root.mkdir()
            write_events(root / "run-p1-baseline" / "events.jsonl", checkpointed_arm())
            write_events(root / "run-p1-treated" / "events.jsonl", checkpointed_arm())
            (root / "2026-07-08-closeout.md").write_text("closeout\n", encoding="utf-8")
            result = ascs.generic_experiment_measurement(root)
        self.assertEqual(result["experiment_status"], "STOPPED / no valid comparison")

    def test_measure_cli_requires_exactly_one_selector(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            with quiet() as (_out, err):
                status_both = ascs.measure_experiment(
                    argparse.Namespace(
                        experiment="004", experiment_dir=str(root), experiments_dir=str(root)
                    )
                )
            with quiet() as (_out, err2):
                status_neither = ascs.measure_experiment(
                    argparse.Namespace(experiment=None, experiment_dir=None, experiments_dir=str(root))
                )
        self.assertEqual(status_both, 1)
        self.assertEqual(status_neither, 1)
        self.assertIn("exactly one", err.getvalue())
        self.assertIn("exactly one", err2.getvalue())

    def test_measure_cli_experiment_dir_prints_report(self):
        with TemporaryDirectory() as tmp:
            root = make_exp004_fixture(tmp)
            with quiet() as (out, _err):
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment=None, experiment_dir=str(root), format="text")
                )
        self.assertEqual(status, 0)
        self.assertIn("ASCS MEASURE RESULT", out.getvalue())
        self.assertIn("VOID condition 3", out.getvalue())

    def test_measure_cli_experiment_dir_fails_without_events(self):
        with TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with quiet() as (_out, err):
                status = ascs.measure_experiment(
                    argparse.Namespace(experiment=None, experiment_dir=str(empty), format="text")
                )
        self.assertEqual(status, 1)
        self.assertIn("no events.jsonl", err.getvalue())


if __name__ == "__main__":
    unittest.main()
