"""Regression checks for the optional, independently written face-crop retouch.

Does NOT require GFPGAN model or Photoshop. Visual evaluation with real
consented photos remains mandatory before changing production defaults.
"""
import unittest

import numpy as np

from signprint_ai.face_module.portrait_gentle import gentle_blend_face


class GentlePortraitTests(unittest.TestCase):
    def test_zero_strength_keeps_original_exactly(self):
        core = np.arange(96 * 96 * 3, dtype=np.uint32).reshape(96, 96, 3).astype(np.uint8)
        fake = 255 - core
        result = gentle_blend_face(core, fake, alpha=0)
        np.testing.assert_array_equal(result, core)

    def test_equal_inputs_are_unchanged(self):
        core = np.full((80, 80, 3), 127, dtype=np.uint8)
        np.testing.assert_array_equal(gentle_blend_face(core, core, alpha=.4), core)

    def test_never_changes_dimensions_or_inputs(self):
        core = np.full((128, 128, 3), 75, dtype=np.uint8)
        proposed = np.full((128, 128, 3), 170, dtype=np.uint8)
        original_copy = core.copy()
        proposal_copy = proposed.copy()
        result = gentle_blend_face(core, proposed, alpha=.45)
        self.assertEqual(result.shape, core.shape)
        self.assertEqual(result.dtype, np.uint8)
        np.testing.assert_array_equal(core, original_copy)
        np.testing.assert_array_equal(proposed, proposal_copy)

    def test_reduces_extreme_candidate_drift(self):
        core = np.full((128, 128, 3), 30, dtype=np.uint8)
        proposed = np.full((128, 128, 3), 250, dtype=np.uint8)
        out = gentle_blend_face(core, proposed, alpha=.45)
        self.assertLess(float(out.mean()), 85)
        self.assertGreater(float(out.mean()), 30)

    def test_keeps_high_contrast_boundaries_better_than_flat_area(self):
        core = np.full((128, 128, 3), 30, dtype=np.uint8)
        core[:, 64:] = 220
        proposed = core.copy()
        proposed[:, :64] = 180
        out = gentle_blend_face(core, proposed, alpha=.45)
        self.assertLess(int(out[64, 63, 0]), int(out[64, 20, 0]))

    def test_invalid_image_sizes_raise(self):
        with self.assertRaises(ValueError):
            gentle_blend_face(
                np.zeros((16, 16, 3), dtype=np.uint8),
                np.zeros((8, 16, 3), dtype=np.uint8),
            )

    def test_invalid_alpha_raises(self):
        a = np.zeros((20, 20, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            gentle_blend_face(a, a, alpha=float("nan"))


if __name__ == "__main__":
    unittest.main()
