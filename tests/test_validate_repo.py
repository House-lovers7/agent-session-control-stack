import importlib.util
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


if __name__ == "__main__":
    unittest.main()
