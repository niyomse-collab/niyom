"""Research-only red ink non-regression: tiny Thai-like strokes and styled gradient.

The real-weight official V2 A/B is a SEPARATE workflow. These CPU tests do
not certify glyph topology, GPU quality, or commercial print acceptance.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw

from signprint_ai.v211_source_guided_ink import source_guided_red_ink


def _lower(image):
    small = Image.fromarray(image, "RGB").resize(
        (image.shape[1] // 2, image.shape[0] // 2),
        Image.Resampling.LANCZOS,
    )
    return cv2.GaussianBlur(np.asarray(small).copy(), (0, 0), .6)


def test_thin_red_diacritic_like_strokes_bypass_repair_exactly():
    art = Image.new("RGB", (256, 192), (62, 58, 86))
    pen = ImageDraw.Draw(art)
    for x in range(18, 230, 9):
        pen.line((x, 25, x, 165), fill=(244, 27, 29), width=2)
    clean = np.asarray(art).copy()
    source = _lower(clean)
    corrupted = clean.copy()
    # A wrong-colour pixel is not permission to change an unresolvable
    # thin stroke into a different glyph or to remove a mark.
    mask = (corrupted[:, :, 0] > 160) & (corrupted[:, :, 1] < 80)
    corrupted[mask, 0] = 170
    corrected, audit = source_guided_red_ink(corrupted, source)
    np.testing.assert_array_equal(corrected, corrupted)
    assert audit["quality_certified"] is False


def test_intentional_red_gradient_is_not_replaced_by_flat_palette():
    h, w = 192, 256
    canvas = np.full((h, w, 3), (62, 58, 86), dtype=np.uint8)
    # A horizontally varying red fill is an intentional typography/effect
    # colour, not AI noise. The LR core must veto automatic recolouring.
    ramp = np.linspace(140, 245, 160).astype(np.uint8)
    canvas[42:142, 48:208, 0] = ramp
    canvas[42:142, 48:208, 1] = 32
    canvas[42:142, 48:208, 2] = 36
    source = _lower(canvas)
    candidate = canvas.copy()
    # V2-like noise in red pigment must not persuade the experiment to
    # flatten a real designed gradient.
    yy, xx = np.indices((100, 160))
    candidate[42:142, 48:208, 0] = np.maximum(
        candidate[42:142, 48:208, 0].astype(np.int16)
        - np.rint(5 + 13 * (1 + np.sin(xx / 4 + yy / 7))).astype(np.int16),
        0,
    ).astype(np.uint8)
    restored, audit = source_guided_red_ink(candidate, source)
    np.testing.assert_array_equal(restored, candidate)
    assert audit["reason"] == "source_gradient_keep_v2"
    assert not audit["quality_certified"]


def test_rgb_mask_never_adds_new_letter_pixels_outside_v2_support():
    image = Image.new("RGB", (256, 192), (62, 58, 86))
    draw = ImageDraw.Draw(image)
    draw.rectangle((38, 51, 146, 139), fill=(242, 28, 31))
    clean = np.asarray(image).copy()
    source = _lower(clean)
    v2 = clean.copy()
    mask = (clean[:, :, 0] > 200) & (clean[:, :, 1] < 70)
    yy, xx = np.indices(mask.shape)
    v2[mask, 0] = (210 + 12 * np.sin(xx[mask] / 5)).astype(np.uint8)
    restored, audit = source_guided_red_ink(v2, source)
    # Every non-red pixel stays intact; no retyped/generated glyph geometry.
    np.testing.assert_array_equal(restored[~mask], v2[~mask])
    assert restored.shape == v2.shape
    assert audit["quality_certified"] is False
