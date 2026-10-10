import unittest
import numpy as np
import cv2
from signprint_ai.portrait import PortraitSettings, process_portrait

class PortraitTests(unittest.TestCase):
    def test_noise_and_geometry(self):
        rng = np.random.default_rng(4)
        image = np.clip(128 + rng.normal(0, 9, (72, 80, 3)), 0, 255).astype(np.uint8)
        out, info = process_portrait(image, PortraitSettings(scale=2, denoise=1, detail=0))
        self.assertEqual(out.shape, (144, 160, 3))
        self.assertLess(float(out.std()), float(image.std()) * .7)
        self.assertFalse(info['ai_used'])

    def test_no_processing_is_identity(self):
        image = np.random.default_rng(1).integers(0, 256, (40, 50, 3), dtype=np.uint8)
        out, _ = process_portrait(image, PortraitSettings(scale=1, denoise=0, detail=0))
        np.testing.assert_array_equal(out, image)

    def test_bounded_ai_and_cancel(self):
        image = np.full((40, 50, 3), 100, np.uint8)
        out, info = process_portrait(image, PortraitSettings(scale=2, detail=0, ai_blend=.5),
            upscale=lambda rgb, scale, cancel: np.full((80, 100, 3), 255, np.uint8))
        self.assertTrue(info['ai_used'])
        self.assertLessEqual(int(out.max()), 109)
        with self.assertRaises(InterruptedError):
            process_portrait(image, cancel=lambda: True)
        with self.assertRaises(ValueError):
            process_portrait(image, PortraitSettings(max_pixels=1))

    def test_tile_context(self):
        image = np.random.default_rng(2).integers(90, 150, (73, 91, 3), dtype=np.uint8)
        small, _ = process_portrait(image, PortraitSettings(scale=1, tile=32, detail=0))
        whole, _ = process_portrait(image, PortraitSettings(scale=1, tile=256, detail=0))
        self.assertLessEqual(int(np.abs(small.astype(int)-whole.astype(int)).max()), 1)
