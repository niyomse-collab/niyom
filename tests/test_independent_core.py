"""Independent core checks requiring no downloaded model or working NVIDIA GPU."""
from __future__ import annotations

import ast
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from independent_core.compare import compare_png
from independent_core.engine import CoreConfig, IndependentCore

ROOT = Path(__file__).resolve().parents[1]

# Git blob hashes from the known working MAIN snapshot, not file-size heuristics.
FROZEN = {
    "signprint_ai/app_v2.py": "be6a759f5f3d4ee9aa7a0daf0d838a7f2916e8d4",
    "signprint_ai/arm_core_adapter.py": "b637440a878e0e3db1a5dc7d9b8953de3f6b7d4c",
    "app/device/device_manager.py": "8b0350066172f7c265aef7662729789d7e1f5a11",
    "app/engine/engine_manager.py": "d99745bc8e3429fd063588e054b5d7c8592fd09f",
    "app/engine/realesrgan_engine.py": "90d1c966bcb689bb2978993f336ed64cad1d2470",
    "signprint_ai/processing.py": "ba761264ca1699c64d6c9ee2fadc133db7b36629",
    "run.py": "c15985a30d4ecaa38ae537dcdb8bc978fb7a1257",
}


class DummyUpsampler:
    def __init__(self):
        self.calls = []

    def enhance(self, pixels, outscale=4):
        self.calls.append(outscale)
        return np.repeat(np.repeat(pixels, outscale, axis=0), outscale, axis=1), "RGB"


class TestIsolatedCore(unittest.TestCase):
    def test_existing_ui_processing_and_core_files_are_bit_for_bit_unchanged(self):
        for path, expected in FROZEN.items():
            with self.subTest(path=path):
                actual = subprocess.check_output(
                    ["git", "hash-object", path], cwd=ROOT, text=True
                ).strip()
                self.assertEqual(actual, expected)

    def test_buttons_have_original_handler_connections(self):
        tree = ast.parse((ROOT / "signprint_ai/app_v2.py").read_text(encoding="utf-8"))
        handlers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "command":
                if isinstance(node.value, ast.Attribute):
                    handlers.add(node.value.attr)
                elif isinstance(node.value, ast.Lambda):
                    for inner in ast.walk(node.value):
                        if isinstance(inner, ast.Attribute):
                            handlers.add(inner.attr)
        expected = {
            "choose_files", "start_processing", "stop_processing",
            "open_output_folder", "choose_output_dir", "remove_selected",
            "_clear_all_files", "_choose_icc_profile", "_settings_changed",
        }
        self.assertTrue(expected.issubset(handlers), expected - handlers)

    def test_experiment_does_not_import_arm_application(self):
        tree = ast.parse((ROOT / "independent_core/engine.py").read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertTrue({"app", "signprint_ai"}.isdisjoint(roots))

    def test_rgb_parity_input_and_2x_4x_8x_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "model.pth").write_bytes(b"dummy")
            original = np.array([[[255, 0, 10], [0, 40, 255]]], dtype=np.uint8)
            source = folder / "input.png"
            Image.fromarray(original).save(source)
            for scale, calls in ((2, [2]), (4, [4]), (8, [4, 2])):
                with self.subTest(scale=scale):
                    core = IndependentCore(CoreConfig(folder / "model.pth"))
                    fake = DummyUpsampler()
                    core._upsampler = fake
                    out = folder / f"result-{scale}.png"
                    info = core.enhance(source, out, scale=scale)
                    self.assertEqual(fake.calls, calls)
                    self.assertEqual(info["output_size"], (2 * scale, scale))
                    expected = np.repeat(np.repeat(original, scale, axis=0), scale, axis=1)
                    with Image.open(out) as im:
                        np.testing.assert_array_equal(np.asarray(im), expected)

    def test_alpha_retained_and_no_input_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "model.pth").write_bytes(b"dummy")
            source = folder / "a.png"
            Image.fromarray(np.array([[[10, 20, 30, 100]]], dtype=np.uint8), mode="RGBA").save(source)
            core = IndependentCore(CoreConfig(folder / "model.pth"))
            core._upsampler = DummyUpsampler()
            with self.assertRaises(ValueError):
                core.enhance(source, source, scale=2)
            target = folder / "out.png"
            core.enhance(source, target, scale=2)
            with Image.open(target) as im:
                self.assertEqual(im.mode, "RGBA")
                self.assertEqual(im.getpixel((0, 0)), (10, 20, 30, 100))

    def test_compare_reports_pixel_difference_and_size_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            a = np.full((2, 3, 3), 100, dtype=np.uint8)
            src, dst = folder / "base.png", folder / "new.png"
            Image.fromarray(a).save(src)
            Image.fromarray(a.copy()).save(dst)
            self.assertTrue(compare_png(src, dst)["same_pixels"])
            a[0, 0, 0] += 1
            Image.fromarray(a).save(dst)
            self.assertEqual(compare_png(src, dst)["changed_pixels"], 1)
            Image.fromarray(a[:1]).save(dst)
            self.assertFalse(compare_png(src, dst)["same_dimensions"])

    def test_missing_weights_fail_safely(self):
        with self.assertRaises(FileNotFoundError):
            IndependentCore(CoreConfig("no-such-file-20261010.pth"))


if __name__ == "__main__":
    unittest.main()
