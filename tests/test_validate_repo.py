import importlib.util
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_repo.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_repo", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestValidateRepo(unittest.TestCase):
    def test_current_repository_passes(self):
        validator = load_validator()
        self.assertEqual(validator.validate(REPO_ROOT), [])

    def test_missing_internal_link_is_reported(self):
        validator = load_validator()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[missing](docs/nope.md)\n", encoding="utf-8")
            errors = validator.validate_internal_links(root)
        self.assertTrue(any("docs/nope.md" in error for error in errors))

    def test_broad_bash_preapproval_is_rejected(self):
        validator = load_validator()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = root / "plugins" / "ascs" / "commands" / "doctor.md"
            command.parent.mkdir(parents=True)
            command.write_text(
                "---\nallowed-tools: Bash(bash *)\n---\n", encoding="utf-8"
            )
            errors = validator.validate_doctor_command(root)
        self.assertTrue(any("allowed-tools" in error for error in errors))

    def copy_paths(self, root, paths):
        for relative in paths:
            source = REPO_ROOT / relative
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def test_current_upstream_lock_is_complete_and_consistent(self):
        validator = load_validator()
        self.assertEqual(validator.validate_upstream_lock(REPO_ROOT, require=True), [])

    def test_upstream_lock_rejects_unpinned_operational_command(self):
        validator = load_validator()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_paths(
                root,
                (
                    "config/upstreams.lock.json",
                    ".claude-plugin/marketplace.json",
                    "docs/upstream-compatibility.md",
                    *validator.OPERATIONAL_PXPIPE_PATHS,
                ),
            )
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "pxpipe-proxy@0.8.0", "pxpipe-proxy", 1
                ),
                encoding="utf-8",
            )
            errors = validator.validate_upstream_lock(root, require=True)
        self.assertTrue(any("must pin @0.8.0" in error for error in errors))

    def test_current_state_scaffolds_satisfy_trust_contract(self):
        validator = load_validator()
        self.assertEqual(validator.validate_state_scaffolds(REPO_ROOT), [])

    def test_state_scaffold_rejects_expiry_over_seven_days(self):
        validator = load_validator()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = (
                *validator.STATE_METADATA_FILES,
                *validator.STATE_PROTOCOL_FILES,
                "examples/codex/.agent-session/.gitignore",
                "examples/claude-code/stack-demo/.agent-session/.gitignore",
                ".gitignore",
                "docs/state-trust-contract.md",
            )
            self.copy_paths(root, required)
            handoff = root / "examples/claude-code/stack-demo/.agent-session/handoff.md"
            handoff.write_text(
                handoff.read_text(encoding="utf-8").replace(
                    "2026-07-17T00:00:00+00:00", "2026-07-18T00:00:00+00:00"
                ),
                encoding="utf-8",
            )
            errors = validator.validate_state_scaffolds(root)
        self.assertTrue(any("within 7 days" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
