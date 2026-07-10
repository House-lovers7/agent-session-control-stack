import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


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

    def test_utc_z_times_are_supported_on_python_39(self):
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


if __name__ == "__main__":
    unittest.main()
