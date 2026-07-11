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

import ascs  # noqa: E402
import exp005  # noqa: E402


# Frozen-evidence tree pinning (the 004 precedent). Arm directories are
# pinned at pre-registration time, when they exist and are frozen; until
# then only the shared scaffold is pinned.
FROZEN_EXP005_TREES = {
    "experiments/2026-07-11-claude-code-restart-005-shared-scaffold": (
        "f24334c36ba3cbf259d810ca009b3e6492199280"
    ),
}

RUNTIME_ARGS = {
    "model": "claude-opus-4-8",
    "effort": "high",
    "approval_mode": "auto",
    "fast_mode": "off",
    "claude_code_version": "2.1.0",
}

RUNTIME_NOTE = (
    "runtime_model=claude-opus-4-8; runtime_effort=high; "
    "runtime_approval_mode=auto; runtime_fast_mode=off; "
    "runtime_cli_version=2.1.0"
)


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


def isolation_event(**overrides: str) -> dict[str, str]:
    fields = {
        "runtime_model": "claude-opus-4-8",
        "runtime_effort": "high",
        "runtime_approval_mode": "auto",
        "runtime_fast_mode": "off",
        "runtime_cli_version": "2.1.0",
    }
    fields.update(overrides)
    note = "isolation-setup; checkout_id: test; base commit: " + "a" * 40
    for key, value in fields.items():
        note += f"; {key}={value}"
    return {"event": "isolation-setup", "note": note}


class TestFrozenEvidence(unittest.TestCase):
    def test_frozen_exp005_trees_match_the_frozen_snapshot(self):
        for path, expected_tree in FROZEN_EXP005_TREES.items():
            self.assertEqual(git(REPO_ROOT, "rev-parse", f"HEAD:{path}"), expected_tree)
            proc = subprocess.run(
                ["git", "diff", "--quiet", "--", path],
                cwd=str(REPO_ROOT),
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"frozen evidence changed: {path}")


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
        for name in exp005.ARMS:
            arm = exp005.arm_from_name(name)
            for phase in ("first", "resume"):
                prompt = exp005.build_prompt(arm, phase)
                self.assertIn("Experiment 005", prompt) if phase == "first" else self.assertIn("checkpoint", prompt)
                for token in forbidden:
                    self.assertNotIn(token, prompt, f"{name}/{phase} contains {token!r}")

    def test_prompts_never_name_runtime_conditions(self):
        # Runtime standardization is operator-side; naming it to the worker
        # would be coaching about the experiment apparatus.
        for name in exp005.ARMS:
            arm = exp005.arm_from_name(name)
            for phase in ("first", "resume"):
                prompt = exp005.build_prompt(arm, phase)
                for token in ("Opus", "effort", "approval mode", "fast mode", "runtime_"):
                    self.assertNotIn(token, prompt, f"{name}/{phase} contains {token!r}")

    def test_condition_prompts_share_same_template(self):
        left = exp005.build_prompt(exp005.arm_from_name("005-p1-baseline"), "first")
        right = exp005.build_prompt(exp005.arm_from_name("005-p1-treated"), "first")
        self.assertEqual(left, right)

    def test_resume_prompt_is_minimal(self):
        prompt = exp005.build_prompt(exp005.arm_from_name("005-p2-treated"), "resume")
        self.assertIn("前回の fresh session は checkpoint で終了しました。同じタスクを完了してください。", prompt)
        self.assertIn("Done definition:", prompt)
        self.assertNotIn("Report and wait", prompt)

    def test_t_b_prompt_freezes_no_primary_key_checkpoint_constraint(self):
        prompt = exp005.build_prompt(exp005.arm_from_name("005-p2-baseline"), "first")
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
            status = exp005.verify_baseline_setup(self.repo)
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
            status = exp005.setup_treated(self.repo)
        self.assertEqual(status, 0)
        claude = (self.repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(claude.count(exp005.MARKER_BEGIN), 1)
        self.assertEqual(claude.count(exp005.MARKER_END), 1)
        source = exp005.frozen_shared_scaffold_path()
        dest = self.repo / ".agent-session"
        self.assertEqual(self.scaffold_files(dest), self.scaffold_files(source))
        for rel in self.scaffold_files(source):
            self.assertEqual(
                (dest / rel).read_text(encoding="utf-8"),
                (source / rel).read_text(encoding="utf-8"),
                str(rel),
            )
        self.assertEqual(exp005.scaffold_tree_hash(source), exp005.scaffold_tree_hash(dest))

    def test_treated_setup_rejects_existing_agent_session_without_removing_it(self):
        existing = self.repo / ".agent-session/stale.md"
        existing.parent.mkdir()
        existing.write_text("stale\n", encoding="utf-8")
        with quiet() as (_out, err):
            status = exp005.setup_treated(self.repo)
        self.assertEqual(status, 1)
        self.assertIn("contamination risk", err.getvalue())
        self.assertTrue(existing.exists())
        self.assertEqual(existing.read_text(encoding="utf-8"), "stale\n")

    def test_isolation_setup_note_records_runtime_and_redacts_machine_identity(self):
        with quiet():
            status = exp005.setup_treated(self.repo)
        self.assertEqual(status, 0)
        runtime_fields = {
            "runtime_model": "claude-opus-4-8",
            "runtime_effort": "high",
            "runtime_approval_mode": "auto",
            "runtime_fast_mode": "off",
            "runtime_cli_version": "2.1.0",
        }
        note = exp005.isolation_setup_note(
            exp005.arm_from_name("005-p1-treated"),
            self.repo,
            "a" * 40,
            runtime_fields,
        )
        self.assertIn("checkout_id: 005-p1-treated", note)
        self.assertIn("verified equal locally", note)
        self.assertIn(RUNTIME_NOTE, note)
        self.assertNotIn(str(self.repo), note)
        self.assertNotIn("sha256:", note)
        self.assertNotIn("/Users/", note)


class TestRuntimeStandardization(unittest.TestCase):
    def prepare_args(self, **overrides):
        values = dict(RUNTIME_ARGS)
        values.update(overrides)
        return argparse.Namespace(
            arm="005-p1-baseline",
            target_repo="/nonexistent",
            sandbox_root="/nonexistent",
            base="HEAD",
            **values,
        )

    def test_runtime_fields_reject_empty_and_separator_values(self):
        for overrides in (
            {"model": ""},
            {"effort": "  "},
            {"approval_mode": "auto; then manual"},
            {"claude_code_version": "2.1.0\n2.2.0"},
        ):
            with quiet():
                fields, status = exp005.runtime_fields_from_args(self.prepare_args(**overrides))
            self.assertEqual(status, 1, overrides)
            self.assertIsNone(fields)

    def test_recorded_runtime_fields_parse_isolation_setup_note(self):
        arm = exp005.arm_from_name("005-p1-baseline")
        with mock.patch.object(exp005, "load_events", return_value=[isolation_event()]):
            fields = exp005.recorded_runtime_fields(arm)
        self.assertEqual(fields["runtime_model"], "claude-opus-4-8")
        self.assertEqual(fields["runtime_cli_version"], "2.1.0")

    def consistency_error(self, recorded_by_arm, arm_name, new_fields):
        def load(arm):
            return recorded_by_arm.get(arm.name, [])

        with mock.patch.object(exp005, "load_events", side_effect=load):
            return exp005.runtime_consistency_error(
                exp005.arm_from_name(arm_name), new_fields
            )

    def new_fields(self, **overrides):
        fields = {
            "runtime_model": "claude-opus-4-8",
            "runtime_effort": "high",
            "runtime_approval_mode": "auto",
            "runtime_fast_mode": "off",
            "runtime_cli_version": "2.1.0",
        }
        fields.update(overrides)
        return fields

    def test_global_field_mismatch_refused_across_pairs(self):
        recorded = {"005-p1-baseline": [isolation_event()]}
        error = self.consistency_error(
            recorded, "005-p2-treated", self.new_fields(runtime_model="claude-sonnet-5")
        )
        self.assertIsNotNone(error)
        self.assertIn("runtime_model", error)
        self.assertIn("void condition 7", error)

    def test_cli_version_mismatch_refused_within_pair_only(self):
        recorded = {"005-p1-baseline": [isolation_event()]}
        within_pair = self.consistency_error(
            recorded, "005-p1-treated", self.new_fields(runtime_cli_version="2.2.0")
        )
        self.assertIsNotNone(within_pair)
        self.assertIn("runtime_cli_version", within_pair)
        across_pairs = self.consistency_error(
            recorded, "005-p2-treated", self.new_fields(runtime_cli_version="2.2.0")
        )
        self.assertIsNone(across_pairs)

    def test_matching_fields_pass(self):
        recorded = {
            "005-p1-baseline": [isolation_event()],
            "005-p1-treated": [isolation_event()],
        }
        self.assertIsNone(
            self.consistency_error(recorded, "005-p2-treated", self.new_fields())
        )

    def test_prepare_arm_refuses_runtime_mismatch_before_touching_repos(self):
        recorded = {"005-p1-baseline": [isolation_event()]}

        def load(arm):
            return recorded.get(arm.name, [])

        args = self.prepare_args(model="claude-sonnet-5")
        args.arm = "005-p1-treated"
        with mock.patch.object(exp005, "load_events", side_effect=load), mock.patch.object(
            exp005, "ensure_git_worktree"
        ) as worktree, mock.patch.object(exp005, "record_event", return_value=0) as record:
            with quiet() as (_out, err):
                status = exp005.command_prepare_arm(args)
        self.assertEqual(status, 1)
        worktree.assert_not_called()
        record.assert_not_called()
        self.assertIn("runtime_model mismatch", err.getvalue())

    def test_record_interruption_requires_runtime_attestation(self):
        args = argparse.Namespace(
            arm="005-p1-baseline",
            checkout="/nonexistent",
            slice1_suite_green=True,
            checkpoint_suite_red_only_slice2=True,
            runtime_conditions_held=False,
            failing_count=3,
        )
        with mock.patch.object(exp005, "checkpoint_signature") as signature, mock.patch.object(
            exp005, "record_event", return_value=0
        ) as record:
            with quiet() as (_out, err):
                status = exp005.command_record_interruption(args)
        self.assertEqual(status, 1)
        signature.assert_not_called()
        record.assert_not_called()
        self.assertIn("--runtime-conditions-held", err.getvalue())
        self.assertIn("void condition 7", err.getvalue())

    def test_record_interruption_note_carries_runtime_attestation(self):
        args = argparse.Namespace(
            arm="005-p1-baseline",
            checkout="/nonexistent",
            slice1_suite_green=True,
            checkpoint_suite_red_only_slice2=True,
            runtime_conditions_held=True,
            failing_count=3,
        )
        signature = {"base": "a" * 40, "head": "b" * 40, "test_count": 1}
        with mock.patch.object(
            exp005, "checkpoint_signature", return_value=(signature, 0)
        ), mock.patch.object(exp005, "record_event", return_value=0) as record:
            with quiet():
                status = exp005.command_record_interruption(args)
        self.assertEqual(status, 0)
        note = record.call_args.args[2]
        self.assertIn("runtime_conditions_held=true", note)


class TestScopeDiffersNote(unittest.TestCase):
    def audit_args(self, **overrides):
        values = {"pair": "1", "scope_differs": False, "note": None}
        values.update(overrides)
        return argparse.Namespace(**values)

    def run_audit(self, args):
        with mock.patch.object(exp005, "has_event", return_value=True), mock.patch.object(
            exp005, "record_pair_event", return_value=0
        ) as record:
            with quiet() as (out, err):
                status = exp005.command_verify_pair_checkpoint(args)
        return status, record, out.getvalue(), err.getvalue()

    def test_scope_differs_without_note_is_refused_with_count_alone_rule(self):
        status, record, _out, err = self.run_audit(self.audit_args(scope_differs=True))
        self.assertEqual(status, 1)
        record.assert_not_called()
        self.assertIn("--note", err)
        self.assertIn("never a sufficient basis", err)

    def test_scope_differs_with_blank_note_is_refused(self):
        status, record, _out, _err = self.run_audit(
            self.audit_args(scope_differs=True, note="   ")
        )
        self.assertEqual(status, 1)
        record.assert_not_called()

    def test_scope_differs_note_rejects_separators(self):
        status, record, _out, _err = self.run_audit(
            self.audit_args(scope_differs=True, note="targets a different rule; honest")
        )
        self.assertEqual(status, 1)
        record.assert_not_called()

    def test_note_without_scope_differs_is_refused(self):
        status, record, _out, _err = self.run_audit(
            self.audit_args(note="looks fine to me")
        )
        self.assertEqual(status, 1)
        record.assert_not_called()

    def test_scope_differs_with_material_note_records_it(self):
        status, record, _out, _err = self.run_audit(
            self.audit_args(
                scope_differs=True,
                note="one arm tests CTAS folding while the other targets policy renames",
            )
        )
        self.assertEqual(status, 0)
        note = record.call_args.args[2]
        self.assertIn("scope_differs=True", note)
        self.assertIn("material_difference=one arm tests CTAS folding", note)

    def test_plain_audit_records_scope_differs_false(self):
        status, record, _out, _err = self.run_audit(self.audit_args())
        self.assertEqual(status, 0)
        note = record.call_args.args[2]
        self.assertIn("scope_differs=False", note)
        self.assertNotIn("material_difference", note)


class TestGitSafetyHelpers(unittest.TestCase):
    def test_porcelain_z_preserves_spaces_newlines_and_rename_sources(self):
        output = " M tests/a b.test.ts\0?? tests/line\nbreak.test.ts\0R  new name.ts\0old name.ts\0"
        self.assertEqual(
            exp005.parse_porcelain_z(output),
            [
                (" M", "tests/a b.test.ts"),
                ("??", "tests/line\nbreak.test.ts"),
                ("R ", "new name.ts"),
                ("R ", "old name.ts"),
            ],
        )

    def test_disable_push_remotes_sets_non_pushable_url_and_no_default(self):
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "remote", "add", "origin", "https://example.invalid/repo.git")
            with quiet():
                status = exp005.disable_push_remotes(repo)
            self.assertEqual(status, 0)
            self.assertEqual(git(repo, "remote", "get-url", "--push", "origin"), exp005.DISABLED_PUSH_URL)
            self.assertEqual(git(repo, "config", "--get", "push.default"), "nothing")

    def test_prepare_failure_packet_is_recoverable_and_does_not_auto_clean(self):
        arm = exp005.arm_from_name("005-p1-baseline")
        checkout = Path("/tmp/example checkout")
        packet = exp005.prepare_recovery_packet(arm, checkout, "a" * 40, "switch-branch")
        self.assertIn("no automatic cleanup", packet)
        self.assertIn("git -C '/tmp/example checkout' status", packet)
        self.assertIn("source repository was not modified", packet)

    def make_source_repo(self, root):
        source = root / "source"
        source.mkdir()
        git(source, "init")
        (source / "README.md").write_text("source\n", encoding="utf-8")
        base = commit_all(source, "base")
        return source, base

    def prepare_args(self, source, base, sandbox):
        return argparse.Namespace(
            arm="005-p1-baseline",
            target_repo=str(source),
            sandbox_root=str(sandbox),
            base=base,
            **RUNTIME_ARGS,
        )

    def test_prepare_arm_isolates_source_and_disables_clone_push(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, base = self.make_source_repo(root)
            original_branch = git(source, "branch", "--show-current")
            sandbox = root / "sandbox"
            with mock.patch.object(exp005, "record_event", return_value=0) as record:
                with quiet():
                    status = exp005.command_prepare_arm(
                        self.prepare_args(source, base, sandbox)
                    )
            self.assertEqual(status, 0)
            self.assertEqual(git(source, "branch", "--show-current"), original_branch)
            self.assertEqual(git(source, "status", "--porcelain"), "")
            checkout = exp005.checkout_path(
                exp005.arm_from_name("005-p1-baseline"), sandbox.resolve()
            )
            self.assertEqual(
                git(checkout, "remote", "get-url", "--push", "origin"),
                exp005.DISABLED_PUSH_URL,
            )
            self.assertEqual(git(checkout, "config", "--get", "push.default"), "nothing")
            isolation_note = record.call_args_list[0].args[2]
            self.assertIn(RUNTIME_NOTE, isolation_note)

    def test_prepare_arm_failure_injection_prints_recovery_without_source_mutation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, base = self.make_source_repo(root)
            sandbox = root / "sandbox"
            with mock.patch.object(exp005, "disable_push_remotes", return_value=1), mock.patch.object(
                exp005, "record_event", return_value=0
            ) as record:
                with quiet() as (_out, err):
                    status = exp005.command_prepare_arm(
                        self.prepare_args(source, base, sandbox)
                    )
            self.assertEqual(status, 1)
            record.assert_not_called()
            self.assertIn("failed stage: disable-push", err.getvalue())
            self.assertIn("no automatic cleanup", err.getvalue())
            self.assertEqual(git(source, "status", "--porcelain"), "")


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
        self.arm = exp005.arm_from_name("005-p1-baseline")

    def test_accepts_one_slice1_commit_plus_uncommitted_test_diff(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("expect(false).toBe(true);\n", encoding="utf-8")
        with mock.patch.object(exp005, "arm_start_base", return_value=self.base):
            with quiet():
                signature, status = exp005.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 0)
        self.assertIsNotNone(signature)
        self.assertEqual(signature["base"], self.base)
        self.assertIn("tests/new_rule.test.ts", signature["test_files"])

    def test_rejects_implementation_diff_at_checkpoint(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("expect(false).toBe(true);\n", encoding="utf-8")
        (self.repo / "src/app.ts").write_text("export const x = 3;\n", encoding="utf-8")
        with mock.patch.object(exp005, "arm_start_base", return_value=self.base):
            with quiet():
                _signature, status = exp005.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 1)

    def test_rejects_committed_claude_experiment_marker(self):
        (self.repo / "CLAUDE.md").write_text(
            f"{exp005.MARKER_BEGIN}\nscaffold\n{exp005.MARKER_END}\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "accidentally commit scaffold")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("test\n", encoding="utf-8")
        with mock.patch.object(exp005, "arm_start_base", return_value=self.base):
            with quiet() as (_out, err):
                _signature, status = exp005.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 1)
        self.assertIn("experiment scaffolding was committed", err.getvalue())

    def test_rejects_committed_agent_session(self):
        (self.repo / ".agent-session").mkdir()
        (self.repo / ".agent-session/handoff.md").write_text("state\n", encoding="utf-8")
        commit_all(self.repo, "accidentally commit state")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/new_rule.test.ts").write_text("test\n", encoding="utf-8")
        with mock.patch.object(exp005, "arm_start_base", return_value=self.base):
            with quiet() as (_out, err):
                _signature, status = exp005.checkpoint_signature(self.arm, self.repo)
        self.assertEqual(status, 1)
        self.assertIn(".agent-session/handoff.md", err.getvalue())


class TestPairTransactions(unittest.TestCase):
    def setUp(self):
        self.state = {name: [] for name in exp005.PAIR_ARMS["1"]}
        self.fail_once = True

    def load(self, arm):
        return list(self.state[arm.name])

    def record_with_injected_failure(self, arm, event_name, note, **metadata):
        if (
            self.fail_once
            and arm.name == "005-p1-treated"
            and event_name == "pair-checkpoint-audit"
        ):
            self.fail_once = False
            return 1
        self.state[arm.name].append({"event": event_name, "note": note})
        return 0

    def test_pair_records_include_structured_schema_metadata(self):
        arm = exp005.arm_from_name("005-p1-baseline")
        with mock.patch.object(exp005, "run_ascs", return_value=0) as run:
            exp005.record_event(
                arm,
                "pair-verdict",
                "verdict",
                pair_id="1",
                condition="baseline",
                transaction_id="tx-1",
            )
        command = run.call_args.args[0]
        self.assertIn("--pair-id", command)
        self.assertIn("--condition", command)
        self.assertIn("--transaction-id", command)

    def test_partial_pair_write_is_aborted_then_retry_commits_idempotently(self):
        transaction_id = "exp005-pair-1-checkpoint-audit-test"
        note = "pair-checkpoint-audit; pair=1; scope_differs=False"
        with mock.patch.object(exp005, "load_events", side_effect=self.load), mock.patch.object(
            exp005, "record_event", side_effect=self.record_with_injected_failure
        ):
            with quiet():
                first = exp005.record_pair_event(
                    "1", "pair-checkpoint-audit", note, transaction_id
                )
            self.assertEqual(first, 1)
            self.assertFalse(exp005.pair_event_committed("1", "pair-checkpoint-audit"))
            self.assertTrue(exp005.pair_event_pending("1", "pair-checkpoint-audit"))
            for name in exp005.PAIR_ARMS["1"]:
                self.assertTrue(
                    any(event["event"] == "pair-event-abort" for event in self.state[name])
                )

            with quiet():
                second = exp005.record_pair_event(
                    "1", "pair-checkpoint-audit", note, transaction_id
                )
            self.assertEqual(second, 0)
            self.assertTrue(exp005.pair_event_committed("1", "pair-checkpoint-audit"))
            self.assertFalse(exp005.pair_event_pending("1", "pair-checkpoint-audit"))

            counts = {name: len(events) for name, events in self.state.items()}
            with quiet():
                third = exp005.record_pair_event(
                    "1", "pair-checkpoint-audit", note, transaction_id
                )
            self.assertEqual(third, 0)
            self.assertEqual(counts, {name: len(events) for name, events in self.state.items()})

    def test_retry_rejects_changed_payload_for_same_transaction(self):
        transaction_id = "exp005-pair-1-void-test"
        with mock.patch.object(exp005, "load_events", side_effect=self.load), mock.patch.object(
            exp005, "record_event", side_effect=self.record_with_injected_failure
        ):
            self.fail_once = False
            with quiet():
                self.assertEqual(
                    exp005.record_pair_event("1", "void-pair", "condition=1a", transaction_id),
                    0,
                )
            with quiet():
                self.assertEqual(
                    exp005.record_pair_event("1", "void-pair", "condition=2", transaction_id),
                    1,
                )

    def test_void_condition_7_is_recordable(self):
        self.assertIn("7", exp005.VOID_CONDITIONS)


class TestRecordAndFinishCommands(unittest.TestCase):
    def make_finish_fixture(self, tmp: str):
        experiment = Path(tmp) / "experiment"
        experiment.mkdir()
        data = {
            "created_at": "2026-07-11T00:00:00+00:00",
            "name": "005-p1-baseline",
            "runtime": "claude-code",
            "target_repo": "supabase-rls-guard",
            "events_file": "events.jsonl",
            "report_file": "report.md",
            "gate_profile": "experiment-005",
            "metrics": {},
            "score": {},
        }
        (experiment / "experiment.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
        events = (
            json.dumps(
                {
                    "timestamp": "2026-07-11T00:00:00+00:00",
                    "event": "resume-start",
                    "note": "start",
                },
                sort_keys=True,
            )
            + "\n"
            + json.dumps(
                {
                    "timestamp": "2026-07-11T00:02:00+00:00",
                    "event": "first-progress-edit",
                    "note": "edit",
                },
                sort_keys=True,
            )
            + "\n"
        )
        report = """# Experiment 005 Preregistration - 005-p1-baseline

## Task Summary

Frozen preregistration task summary.

## Events

- Existing evidence note must survive.

## Result

<!-- Filled after the arm finishes. -->
"""
        (experiment / "events.jsonl").write_text(events, encoding="utf-8")
        (experiment / "report.md").write_text(report, encoding="utf-8")
        return experiment, report, events

    def finish_args(self, **overrides):
        values = dict(
            arm="005-p1-baseline",
            missed_checkpoint_items=1,
            human_corrections=0,
            recovery_quality=4,
            missed_state_files="n/a",
            runtime_conditions_held=True,
        )
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_record_resume_start_requires_pair_audit(self):
        with mock.patch.object(
            exp005, "has_event", side_effect=lambda _arm, event: event == "interruption_reached"
        ), mock.patch.object(exp005, "pair_event_committed", return_value=False), mock.patch.object(
            exp005, "record_event", return_value=0
        ) as record:
            with quiet():
                status = exp005.command_record_resume_start(argparse.Namespace(arm="005-p1-baseline"))
        self.assertEqual(status, 1)
        record.assert_not_called()

    def test_finish_arm_requires_runtime_attestation(self):
        with TemporaryDirectory() as tmp:
            experiment, original_report, original_events = self.make_finish_fixture(tmp)
            original_json = (experiment / "experiment.json").read_text(encoding="utf-8")
            with mock.patch.object(exp005, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp005, "events_path", return_value=experiment / "events.jsonl"):
                with quiet() as (_out, err):
                    status = exp005.command_finish_arm(
                        self.finish_args(runtime_conditions_held=False)
                    )
            self.assertEqual(status, 1)
            self.assertIn("--runtime-conditions-held", err.getvalue())
            self.assertEqual(
                (experiment / "experiment.json").read_text(encoding="utf-8"), original_json
            )
            self.assertEqual((experiment / "report.md").read_text(encoding="utf-8"), original_report)
            self.assertEqual((experiment / "events.jsonl").read_text(encoding="utf-8"), original_events)

    def test_finish_arm_updates_metrics_without_rewriting_report(self):
        with TemporaryDirectory() as tmp:
            experiment, original_report, _original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp005, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp005, "events_path", return_value=experiment / "events.jsonl"):
                with quiet():
                    status = exp005.command_finish_arm(self.finish_args())
            self.assertEqual(status, 0)
            data = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(data["gate_profile"], "experiment-005")
            self.assertEqual(data["metrics"]["resume_time_seconds"], 120)
            self.assertEqual(data["metrics"]["missed_checkpoint_items"], 1)
            self.assertEqual(data["metrics"]["missed_state_files"], "n/a")
            self.assertEqual(data["score"]["status"], "REPORTED_ONLY")
            self.assertEqual((experiment / "report.md").read_text(encoding="utf-8"), original_report)

    def test_finish_arm_leaves_events_file_unchanged(self):
        with TemporaryDirectory() as tmp:
            experiment, _original_report, original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp005, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp005, "events_path", return_value=experiment / "events.jsonl"):
                with quiet():
                    status = exp005.command_finish_arm(self.finish_args())
            self.assertEqual(status, 0)
            self.assertEqual((experiment / "events.jsonl").read_text(encoding="utf-8"), original_events)

    def test_finish_arm_does_not_call_generic_finish_or_score(self):
        with TemporaryDirectory() as tmp:
            experiment, _original_report, _original_events = self.make_finish_fixture(tmp)
            with mock.patch.object(exp005, "experiment_path", return_value=experiment), \
                    mock.patch.object(exp005, "events_path", return_value=experiment / "events.jsonl"), \
                    mock.patch.object(exp005, "run_ascs", return_value=0) as run:
                with quiet():
                    status = exp005.command_finish_arm(self.finish_args())
        self.assertEqual(status, 0)
        run.assert_not_called()


class TestGateProfile005(unittest.TestCase):
    def metrics(self):
        return {
            "resume_time_seconds": 120,
            "missed_checkpoint_items": 0,
            "missed_state_files": "n/a",
            "human_corrections": 0,
            "recovery_quality": 4,
        }

    def test_experiment_005_profile_is_reported_only(self):
        score = ascs.calculate_score(self.metrics(), gate_profile="experiment-005")
        self.assertEqual(score["status"], "REPORTED_ONLY")
        self.assertEqual(score["failed_criteria"], [])
        self.assertEqual(score["gate_profile"], "experiment-005")

    def test_experiment_004_profile_behavior_is_unchanged(self):
        score = ascs.calculate_score(self.metrics(), gate_profile="experiment-004")
        self.assertEqual(score["status"], "REPORTED_ONLY")
        self.assertEqual(score["gate_profile"], "experiment-004")

    def test_default_profile_still_rejects_missed_state_files_na(self):
        metrics = {
            "resume_time_seconds": 120,
            "missed_state_files": "n/a",
            "repeated_failures": 0,
            "rejected_option_relapses": 0,
            "human_corrections": 0,
        }
        with self.assertRaises(ValueError):
            ascs.calculate_score(metrics, gate_profile="default")


if __name__ == "__main__":
    unittest.main()
