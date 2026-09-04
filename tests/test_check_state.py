import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_state  # noqa: E402


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


class TestStateTrustCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init")
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
        self.branch = git(self.repo, "branch", "--show-current")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.state_dir = self.repo / ".agent-session"
        self.state_dir.mkdir()
        self.now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)

    def write_state(
        self,
        repository="example/project",
        branch=None,
        commit=None,
        updated="2026-07-10T00:00:00+00:00",
        expires="2026-07-17T00:00:00+00:00",
        body="recovery hint only",
    ):
        content = f"""<!-- ascs-state-metadata
state_schema_version: 1
repository: {repository}
branch: {branch or self.branch}
commit: {commit or self.commit}
session_id: writer-session-1
updated_at: {updated}
expires_at: {expires}
-->

# Handoff

{body}
"""
        (self.state_dir / "handoff.md").write_text(content, encoding="utf-8")

    def inspect(self, **kwargs):
        return check_state.inspect_state(
            self.repo,
            self.state_dir,
            repository="example/project",
            now=self.now,
            **kwargs,
        )

    def test_valid_state_passes(self):
        self.write_state()
        result = self.inspect()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["issues"], [])

    def test_utc_z_times_are_supported(self):
        self.write_state(
            updated="2026-07-10T00:00:00Z",
            expires="2026-07-17T00:00:00Z",
        )
        self.assertEqual(self.inspect()["status"], "PASS")

    def test_repository_mismatch_fails_and_requires_ignoring_state(self):
        self.write_state(repository="other/project")
        result = self.inspect()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["code"] == "repository_mismatch" for item in result["issues"]))

    def test_commit_mismatch_is_stale(self):
        self.write_state(commit="a" * 40)
        result = self.inspect()
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(any(item["code"] == "commit_mismatch" for item in result["issues"]))

    def test_expired_state_is_stale(self):
        self.write_state(
            updated="2026-07-01T00:00:00+00:00",
            expires="2026-07-08T00:00:00+00:00",
        )
        result = self.inspect()
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(any(item["code"] == "expired" for item in result["issues"]))

    def test_apparent_secret_fails_without_echoing_value(self):
        value = "do-not-echo-this-value"
        self.write_state(body=f"api_key: {value}")
        result = self.inspect()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["code"] == "secret_value" for item in result["issues"]))
        self.assertNotIn(value, str(result))

    def test_repository_remote_parsing(self):
        self.assertEqual(
            check_state.repository_from_remote("git@github.com:owner/project.git"),
            "owner/project",
        )
        self.assertEqual(
            check_state.repository_from_remote("https://github.com/owner/project.git"),
            "owner/project",
        )
        self.assertIsNone(check_state.repository_from_remote("/local/path/project"))

    def test_directory_links_are_rejected_even_without_markdown_files(self):
        with TemporaryDirectory() as outside:
            (Path(outside) / "checkpoint.md").write_text("unvalidated")
            (self.state_dir / "state").symlink_to(outside, target_is_directory=True)
            for with_handoff in (False, True):
                with self.subTest(with_handoff=with_handoff):
                    if with_handoff:
                        self.write_state()
                    self.assertEqual(self.inspect()["status"], "FAIL")

    def test_state_root_link_inside_repo_is_rejected(self):
        self.state_dir.rmdir()
        actual = self.repo / "actual-state"
        actual.mkdir()
        self.state_dir.symlink_to(actual, target_is_directory=True)
        self.write_state()
        self.assertEqual(self.inspect()["status"], "FAIL")

    def test_scan_errors_fail_closed(self):
        self.write_state()
        with patch("os.scandir", side_effect=PermissionError("synthetic")):
            self.assertEqual(self.inspect()["status"], "FAIL")

    def test_markdown_directory_is_not_treated_as_absent_state(self):
        (self.state_dir / "handoff.md").mkdir()
        self.assertEqual(self.inspect()["status"], "FAIL")

    def test_link_in_custom_state_parent_is_rejected(self):
        parent = self.repo / "alias"
        parent.symlink_to(self.state_dir, target_is_directory=True)
        (self.state_dir / "nested").mkdir()
        result = check_state.inspect_state(
            self.repo, parent / "nested", repository="example/project", now=self.now
        )
        self.assertEqual(result["status"], "FAIL")

    def test_file_replaced_with_fifo_before_open_is_rejected(self):
        self.write_state()
        original_open = os.open

        def swap_before_open(path, flags, *args, **kwargs):
            if path == "handoff.md":
                target = self.state_dir / path
                target.unlink()
                os.mkfifo(target)
                # This assertion prevents a regressed implementation from hanging the test.
                self.assertTrue(flags & os.O_NONBLOCK)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(check_state.os, "open", side_effect=swap_before_open):
            self.assertEqual(self.inspect()["status"], "FAIL")

    def test_malformed_metadata_is_not_echoed_by_cli(self):
        for insertion in ("SYNTHETIC_PRIVATE_LINE", "SYNTHETIC_PRIVATE_KEY: a\nSYNTHETIC_PRIVATE_KEY: b"):
            with self.subTest(insertion=insertion):
                self.write_state()
                path = self.state_dir / "handoff.md"
                path.write_text(path.read_text().replace("state_schema_version: 1", insertion + "\nstate_schema_version: 1"))
                for output_args in ([], ["--json"]):
                    proc = subprocess.run(
                        [sys.executable, "-B", str(REPO_ROOT / "scripts/check_state.py"),
                         "--repo", str(self.repo), "--repository", "example/project", *output_args],
                        capture_output=True, text=True, timeout=3,
                    )
                    self.assertEqual(proc.returncode, 1)
                    self.assertNotIn("SYNTHETIC_PRIVATE", proc.stdout + proc.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO")
    def test_fifo_is_rejected_without_waiting_for_writer(self):
        os.mkfifo(self.state_dir / "handoff.md")
        proc = subprocess.run(
            [sys.executable, "-B", str(REPO_ROOT / "scripts/check_state.py"),
             "--repo", str(self.repo), "--repository", "example/project", "--json"],
            capture_output=True, text=True, timeout=3,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["status"], "FAIL")

    def test_rollback_is_excluded_and_regular_state_still_passes(self):
        self.write_state()
        rollback = self.state_dir / ".rollback"
        rollback.mkdir()
        (rollback / "old.md").write_text("expired unvalidated backup")
        self.assertEqual(self.inspect()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
