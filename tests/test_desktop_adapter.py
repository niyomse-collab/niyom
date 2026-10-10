"""No-model dry runs verify desktop settings/output safety; no NVIDIA needed."""
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

import numpy as np
from PIL import Image

from independent_core.desktop_adapter import DesktopTestAdapter, DeviceView
from signprint_ai.processing import EnhanceSettings


class FakeModel:
    def enhance(self, source, output, scale, progress_callback=None, cancel_check=None):
        with Image.open(source) as im:
            pixels = np.asarray(im.convert("RGB"))
        out = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        Image.fromarray(out).save(output, "PNG")
        if progress_callback:
            progress_callback(100)


class AdapterWithoutNeuralWeights(DesktopTestAdapter):
    @property
    def available(self):
        return True

    def default_device(self):
        return DeviceView("CPU-TEST", "cpu", "CPU")


class DesktopAdapterContract(unittest.TestCase):
    def test_end_to_end_test_adapter_png_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "in.png"
            dest = Path(folder) / "in_NiyomSilp_CoreTEST.png"
            image = np.full((3, 4, 3), 112, dtype=np.uint8)
            image[0, 0] = (255, 0, 0)
            Image.fromarray(image).save(source)
            adapter = AdapterWithoutNeuralWeights()
            adapter._engine = FakeModel()
            values = []
            settings = EnhanceSettings(ai_scale=2, dpi=300, color_mode="RGB",
                                       face_protection=False)
            info = adapter.process(source, dest, settings,
                                   progress=lambda v, msg: values.append(v))
            self.assertEqual(info["output_size"], (8, 6))
            self.assertEqual(info["engine"], "NiyomSilp Independent Core TEST")
            self.assertEqual(values[-1], 100)
            with Image.open(dest) as out:
                self.assertEqual(out.size, (8, 6))
                self.assertEqual(out.getpixel((0, 0)), (255, 0, 0))
            before = dest.read_bytes()
            with self.assertRaises(FileExistsError):
                adapter.process(source, dest, settings)
            self.assertEqual(before, dest.read_bytes())
            self.assertTrue(source.exists())

    def test_print_size_aspect_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "original.png"
            dest = Path(folder) / "test.png"
            Image.new("RGB", (13, 7), "red").save(source)
            adapter = AdapterWithoutNeuralWeights()
            adapter._engine = FakeModel()
            settings = EnhanceSettings(ai_scale=2, dpi=72, color_mode="RGB",
                                       print_width=3, print_height=3,
                                       print_unit="cm")
            info = adapter.process(source, dest, settings)
            self.assertEqual(info["output_size"], (85, 85))
            with Image.open(dest) as out:
                self.assertEqual(out.size, (85, 85))
                self.assertEqual(out.getpixel((0, 0)), (255, 255, 255))

    def test_cancel_is_respected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            dest = Path(folder) / "result.png"
            Image.new("RGB", (9, 9), "white").save(source)
            adapter = AdapterWithoutNeuralWeights()
            with self.assertRaises(InterruptedError):
                adapter.process(source, dest, EnhanceSettings(),
                                cancel=lambda: True)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
