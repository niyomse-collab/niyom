"""Core file immutability regression guard.

These Git blob SHAs are from the proven printing-quality core. A portrait
feature branch must NEVER silently change any of them. Changes to the core
must be a separate, explicit user-approved effort.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = {
    "app/engine/realesrgan_engine.py": "90d1c966bcb689bb2978993f336ed64cad1d2470",
    "app/engine/engine_manager.py": "d99745bc8e3429fd063588e054b5d7c8592fd09f",
    "app/device/device_manager.py": "8b0350066172f7c265aef7662729789d7e1f5a11",
}


class StableCoreTests(unittest.TestCase):
    def test_original_ai_core_git_blobs_unchanged(self):
        for filename, expected_sha in FROZEN.items():
            with self.subTest(file=filename):
                actual = subprocess.check_output(
                    ["git", "hash-object", filename], cwd=ROOT, text=True
                ).strip()
                self.assertEqual(actual, expected_sha)

    def test_extra_features_are_explicitly_opt_in(self):
        # Parsing source text here avoids loading torch/GFPGAN on CI.
        settings = (ROOT / "signprint_ai/processing.py").read_text(encoding="utf-8")
        self.assertIn("face_protection: bool = False", settings)
        self.assertIn("portrait_gentle: bool = False", settings)
        adapter = (ROOT / "signprint_ai/arm_core_adapter.py").read_text(encoding="utf-8")
        self.assertIn('if use_ai and face_info["enabled"]:', adapter)


if __name__ == "__main__":
    unittest.main()
