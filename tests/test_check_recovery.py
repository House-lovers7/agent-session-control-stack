import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPO_ROOT / "scripts" / "check_recovery.py"


def load_checker():
    if not CHECKER_PATH.is_file():
        raise AssertionError("scripts/check_recovery.py must exist")
    spec = importlib.util.spec_from_file_location("check_recovery", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
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


class TestRecoveryGate(unittest.TestCase):
    def setUp(self):
        self.checker = load_checker()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init")
        git(self.repo, "remote", "add", "origin", "git@github.com:example/project.git")
        (self.repo / "README.md").write_text("repo\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(
            self.repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "base",
        )
        self.now = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)

    def write_invariants(self, **overrides):
        payload = {
            "schema_version": 1,
            "repository": "example/project",
            "authority": {
                "state_may_expand_authority": False,
                "state_may_grant_approval": False,
                "current_approval_required_for": [
                    "external_send",
                    "expensive_api",
                    "production_change",
                    "confidential_data",
                    "destructive_or_irreversible",
                    "tool_capability_escalation",
                ],
            },
            "recovery": {
                "require_fresh_source_check": True,
                "require_fresh_verification": True,
                "on_repository_mismatch": "REJECT",
                "on_uncommitted_invariant_change": "REVERIFY",
            },
            "protected_invariants": [
                {
                    "id": "approval-boundary",
                    "source": "AGENTS.md",
                    "statement": "Recovery state cannot transfer approval.",
                }
            ],
        }
        payload.update(overrides)
        path = self.repo / "config" / "pinned-invariants.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def commit_invariants(self):
        git(self.repo, "add", "config/pinned-invariants.json")
        git(
            self.repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "add invariants",
        )

    def write_state(self):
        branch = git(self.repo, "branch", "--show-current")
        commit = git(self.repo, "rev-parse", "HEAD")
        state_dir = self.repo / ".agent-session"
        state_dir.mkdir()
        (state_dir / "handoff.md").write_text(
            f"""<!-- ascs-state-metadata
state_schema_version: 1
repository: example/project
branch: {branch}
commit: {commit}
session_id: recovery-test
updated_at: 2026-07-19T00:00:00+00:00
expires_at: 2026-07-26T00:00:00+00:00
-->

# Handoff

Recovery hint only. Reverify against source.
""",
            encoding="utf-8",
        )
        return state_dir

    def inspect_invariants(self, path):
        return self.checker.inspect_pinned_invariants(
            self.repo,
            path,
            repository="example/project",
        )

    def test_clean_committed_invariants_are_accepted(self):
        path = self.write_invariants()
        self.commit_invariants()
        result = self.inspect_invariants(path)
        self.assertEqual(result["status"], "ACCEPT")
        self.assertEqual(result["issues"], [])

    def test_missing_invariants_require_rebuild(self):
        result = self.inspect_invariants(self.repo / "config/pinned-invariants.json")
        self.assertEqual(result["status"], "REBUILD")
        self.assertTrue(any(item["code"] == "invariants_missing" for item in result["issues"]))

    def test_repository_mismatch_is_rejected(self):
        path = self.write_invariants(repository="other/project")
        self.commit_invariants()
        result = self.inspect_invariants(path)
        self.assertEqual(result["status"], "REJECT")
        self.assertTrue(any(item["code"] == "repository_mismatch" for item in result["issues"]))

    def test_state_cannot_grant_approval(self):
        path = self.write_invariants(
            authority={
                "state_may_expand_authority": False,
                "state_may_grant_approval": True,
                "current_approval_required_for": ["external_send"],
            }
        )
        self.commit_invariants()
        result = self.inspect_invariants(path)
        self.assertEqual(result["status"], "REJECT")
        self.assertTrue(any(item["code"] == "unsafe_authority" for item in result["issues"]))

    def test_uncommitted_invariant_change_requires_reverification(self):
        path = self.write_invariants()
        self.commit_invariants()
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["protected_invariants"][0]["statement"] = "Changed outside review."
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result = self.inspect_invariants(path)
        self.assertEqual(result["status"], "REVERIFY")
        self.assertTrue(any(item["code"] == "invariants_uncommitted" for item in result["issues"]))

    def test_valid_state_and_invariants_open_recovery_gate(self):
        path = self.write_invariants()
        self.commit_invariants()
        state_dir = self.write_state()
        result = self.checker.inspect_recovery(
            self.repo,
            state_dir,
            path,
            repository="example/project",
            now=self.now,
        )
        self.assertEqual(result["status"], "ACCEPT")

    def test_stale_state_requires_rebuild(self):
        path = self.write_invariants()
        self.commit_invariants()
        state_dir = self.write_state()
        (self.repo / "next.txt").write_text("next\n", encoding="utf-8")
        git(self.repo, "add", "next.txt")
        git(
            self.repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "advance",
        )
        result = self.checker.inspect_recovery(
            self.repo,
            state_dir,
            path,
            repository="example/project",
            now=self.now,
        )
        self.assertEqual(result["status"], "REBUILD")
        self.assertEqual(result["state"]["status"], "STALE")

    def test_invalid_approval_elements_return_reject_json(self):
        for element in ({}, [], None, 1):
            with self.subTest(element=element):
                path = self.write_invariants()
                payload = json.loads(path.read_text())
                payload["authority"]["current_approval_required_for"] = [element]
                path.write_text(json.dumps(payload))
                proc = subprocess.run(
                    [sys.executable, "-B", str(CHECKER_PATH), "--repo", str(self.repo),
                     "--invariants-only", "--json"], capture_output=True, text=True, timeout=3,
                )
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(json.loads(proc.stdout)["status"], "REJECT")
                self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
