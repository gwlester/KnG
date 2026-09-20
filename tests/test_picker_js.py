import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class PickerJsTests(unittest.TestCase):
    def test_picker_logic(self):
        result = subprocess.run(
            ["node", "--test", str(ROOT / "tests" / "picker.test.js")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_training_finder_logic(self):
        result = subprocess.run(
            ["node", "--test", str(ROOT / "tests" / "training.test.js")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
