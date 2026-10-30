"""Conservative V2 typography/flat-fill regression tests.

Generated geometric fixtures only: do not add customer artwork to public git.
Passing these tests does NOT certify Photoshop quality or vector reconstruction.
"""
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image

from signprint_ai.v2_graphic_edges import refine_sign_edges


def controls(*, flat=0, text=0):
    return SimpleNamespace(
        denoise=0, flat_smoothing=flat, text_graphic_boost=text,
        sharpness=0,
    )


def specimen():
    width, height = 480, 260
    rng = np.random.default_rng(8)
    x = np.arange(width)[None, :]
    y = np.arange(height)[:, None]
    low_frequency_waves = 6 * np.sin(x / 6.7) + 3 * np.sin(y / 9.5)
    grain = rng.normal(0, 1.7, (height, width))
    beige = np.array([220, 206, 162], dtype=float)
    background = np.clip(
        beige[None, None, :] + (low_frequency_waves + grain)[:, :, None],
        0, 255,
    ).astype(np.uint8)
    # Clean solids and tiny detached mark model signage glyphs and Thai marks.
    cv2.rectangle(background, (70, 76), (410, 107), (20, 44, 110), -1)
    cv2.circle(background, (252, 188), 64, (16, 75, 146), -1)
    cv2.circle(background, (252, 188), 43, (220, 206, 162), -1)
    cv2.circle(background, (236, 63), 7, (20, 44, 110), -1)
    return background


def test_flat_fill_removes_small_waves_away_from_graphic_edges():
    original = specimen()
    corrected = np.asarray(
        refine_sign_edges(Image.fromarray(original), settings=controls(flat=100))
    )
    # Sample the intended uniform background far from graphic contours.
    region = np.s_[20:52, 80:390, 0]
    assert corrected[region].std() < original[region].std() * 0.85
    # Distinct text colours and isolated tone-mark-sized graphic are untouched.
    np.testing.assert_array_equal(corrected[90, 130], original[90, 130])
    np.testing.assert_array_equal(corrected[63, 236], original[63, 236])
    assert np.abs(corrected.astype(int) - original.astype(int)).max() <= 15


def test_contour_following_reduces_one_pixel_straight_stroke_zigzags():
    width = height = 320
    yy, xx = np.mgrid[:height, :width]
    wobble = 130 + np.rint(1.3 * np.sin(0.84 * yy)).astype(int)
    ink = (xx >= wobble).astype(np.float32)
    beige = np.array([236., 225., 184.])
    blue = np.array([15., 45., 150.])
    rgb = beige[None, None, :] * (1 - ink[:, :, None]) + blue[None, None, :] * ink[:, :, None]
    rgb = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), 0.8).astype(np.uint8)
    corrected = np.asarray(refine_sign_edges(Image.fromarray(rgb), settings=controls(text=100)))
    def contour_positions(data):
        return np.argmax(data[10:-10, :, 2] < 170, axis=1).astype(np.float32)
    original_positions = contour_positions(rgb)
    corrected_positions = contour_positions(corrected)
    assert np.std(corrected_positions) < np.std(original_positions) * 0.92
    assert np.max(np.abs(corrected.astype(int) - rgb.astype(int))) <= 111


def test_opaque_boundary_alpha_and_confirmed_face_region_are_preserved():
    rgb = specimen()
    alpha = np.full(rgb.shape[:2], 255, np.uint8)
    alpha[:, :20] = 60
    image = Image.fromarray(np.dstack([rgb, alpha]))
    protected = ((.40, .28, .60, .64),)
    corrected = np.asarray(refine_sign_edges(
        image, settings=controls(flat=100, text=100), protected_regions=protected,
    ))
    np.testing.assert_array_equal(corrected[..., 3], alpha)
    np.testing.assert_array_equal(corrected[:, :24, :3], rgb[:, :24])
    np.testing.assert_array_equal(corrected[75:171, 190:289, :3], rgb[75:171, 190:289])
