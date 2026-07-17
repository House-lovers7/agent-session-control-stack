import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "scripts" / "smoke_codex_compact.py"


def load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_codex_compact", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestCodexCompactSmoke(unittest.TestCase):
    def test_manual_and_auto_subprocess_contracts_are_one_shot_and_private(self):
        smoke = load_smoke()

        result = smoke.run_smoke()

        self.assertEqual(tuple(item["trigger"] for item in result), ("manual", "auto"))
        self.assertTrue(all(item["receipt_consumed_once"] for item in result))
        self.assertTrue(all(item["sensitive_values_absent"] for item in result))

    def test_cli_reports_no_runtime_or_model_execution(self):
        result = subprocess.run(
            [sys.executable, str(SMOKE_PATH)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: Codex compact hook", result.stdout)
        self.assertIn("no Codex/model/API execution", result.stdout)


if __name__ == "__main__":
    unittest.main()
