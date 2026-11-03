"""Preserve vivid CMYK-facing RGB artwork when HAT supplements V2.

The enhancement applies common luminance details to each channel. If one
channel clips but the others do not, the printed brand hue changes. The new
gamut-safe blend must not introduce this distortion.
"""
import numpy as np
from signprint_ai.v211_hat_assist import blend_v2_with_hat


def _saturated_edges():
    v2 = np.empty((64, 64, 3), dtype=np.uint8)
    v2[:, :32] = (225, 25, 40)  # vivid red ink
    v2[:, 32:] = (30, 60, 225)  # vivid blue ink
    hat = v2.copy()
    hat[:, :32] = (245, 45, 60)
    hat[:, 32:] = (10, 40, 205)
    return v2, hat


def test_saturated_ink_preserves_v2_rgb_channel_differences():
    v2, hat = _saturated_edges()
    result = blend_v2_with_hat(v2, hat, strength=1)
    # The HAT assist may enhance edges, but must not clip one saturated
    # channel independently and distort the original V2 brand colours.
    for channel in (1, 2):
        np.testing.assert_array_equal(
            result[:, :, 0].astype("int16") - result[:, :, channel].astype("int16"),
            v2[:, :, 0].astype("int16") - v2[:, :, channel].astype("int16"),
        )


def test_black_and_white_channel_boundaries_cannot_shift_colours():
    v2 = np.zeros((64, 64, 3), dtype=np.uint8)
    v2[:, :32] = (255, 30, 0)
    v2[:, 32:] = (0, 40, 255)
    hat = v2.copy()
    hat[:, :32] = (30, 90, 90)
    hat[:, 32:] = (100, 10, 20)
    result = blend_v2_with_hat(v2, hat, strength=1)
    np.testing.assert_array_equal(result, v2)


def test_face_roi_remains_bitwise_identical_even_on_colour_edge():
    v2, hat = _saturated_edges()
    result = blend_v2_with_hat(
        v2, hat, strength=1, protected_regions=((0.24, 0.24, 0.76, 0.76),)
    )
    np.testing.assert_array_equal(result[16:48, 16:48], v2[16:48, 16:48])


def test_flat_fill_remains_unchanged():
    v2 = np.full((32, 32, 3), (240, 20, 40), dtype=np.uint8)
    hat = np.full_like(v2, (210, 50, 80))
    np.testing.assert_array_equal(
        blend_v2_with_hat(v2, hat, strength=1), v2
    )
