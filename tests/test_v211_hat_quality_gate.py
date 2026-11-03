"""User-reported V2.1.1 visual regression: HAT must not distort V2 outlines.

These deterministic tests cover the failure classes observed when comparing
the actual synthetic V2 and V2+HAT outputs: ghost/ringing strokes, blurred
contours, shifted line boundaries and protected V2 face regions. Passing these
tests cannot certify subjective enhancement or customer print quality.
"""
import cv2
import numpy as np
from signprint_ai.v211_hat_assist import blend_v2_with_hat


def _v2_red_blue():
    base = np.full((64, 96, 3), (20, 150, 150), dtype=np.uint8)
    base[10:42, 8:50] = (235, 25, 40)
    base[10:42, 50:87] = (28, 70, 232)
    base[48:52, 8:87] = (240, 240, 240)
    return base


def test_off_edge_stripes_are_rejected_not_strengthened():
    v2 = _v2_red_blue()
    hat = v2.copy()
    # HAT invents stripes below a crisp V2 line (reported visual failure).
    hat[55:60, 14:78:2, :] = 5
    result = blend_v2_with_hat(v2, hat, strength=1)
    np.testing.assert_array_equal(result[55:60, 14:78], v2[55:60, 14:78])


def test_blurring_the_existing_v2_outline_is_not_an_improvement():
    v2 = _v2_red_blue()
    hat = cv2.GaussianBlur(v2, (9, 9), 2.0)
    result = blend_v2_with_hat(v2, hat, strength=1)
    np.testing.assert_array_equal(result, v2)


def test_shifted_hard_edge_does_not_transfer_a_second_ghost_edge():
    v2 = np.full((64, 64, 3), 28, dtype=np.uint8)
    v2[:, 32:] = 215
    hat = np.full_like(v2, 28)
    hat[:, 36:] = 240  # shifted four pixels: reject double-line artifact
    result = blend_v2_with_hat(v2, hat, strength=1)
    np.testing.assert_array_equal(result, v2)


def test_aligned_crisper_contour_can_gain_bounded_detail():
    v2 = np.full((64, 64, 3), 42, dtype=np.uint8)
    v2[:, 32:] = 208
    hat = np.full_like(v2, 5)
    hat[:, 32:] = 245
    result = blend_v2_with_hat(v2, hat, strength=1)
    assert np.any(result != v2), "Model selection must not be an inert switch"
    assert int(np.abs(result.astype(np.int16)-v2.astype(np.int16)).max()) <= 12
    np.testing.assert_array_equal(result[:, :25], v2[:, :25])
    np.testing.assert_array_equal(result[:, 40:], v2[:, 40:])


def test_synthetic_face_region_remains_exactly_v2():
    v2 = _v2_red_blue()
    hat = np.clip(v2.astype(np.int16) + 30, 0, 255).astype(np.uint8)
    result = blend_v2_with_hat(
        v2, hat, strength=1,
        protected_regions=((0.25, 0.20, 0.80, 0.80),)
    )
    np.testing.assert_array_equal(result[15:50, 25:70], v2[15:50, 25:70])
