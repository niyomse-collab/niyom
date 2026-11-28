"""Automatic styled-effect risk guard regressions.

All rasters here are synthetic. These tests verify conservative pixel gating,
not semantic text detection, native inference, or print quality.
"""
import numpy as np
import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tools.v211_four_engine_fusion import (
    _styled_effect_guard_mask,
    fuse_four_engine_details,
)
from tools.v211_four_engine_coordinator import ENGINES


def _highpass(image, radius):
    gray = image.convert("L")
    values = np.asarray(gray, dtype=np.float32)
    blurred = np.asarray(
        gray.filter(ImageFilter.GaussianBlur(radius=radius)),
        dtype=np.float32,
    )
    return values - blurred


def _save(path, pixels):
    Image.fromarray(pixels.astype(np.uint8), "RGB").save(
        path, format="PNG", dpi=(300, 300)
    )


def _styled_fixture(tmp_path):
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-v2.png"
    Image.new("RGB", (64, 64), (70, 70, 70)).save(
        source, format="PNG", dpi=(300, 300)
    )

    # A single hard contour is the positive control: it should remain eligible.
    base = np.empty((128, 128, 3), dtype=np.uint8)
    base[:, :6] = (70, 70, 70)
    base[:, 6:] = (170, 170, 170)

    # A detached soft shadow behind a flattened headline.
    shadow_mask = Image.new("L", (128, 128), 0)
    ImageDraw.Draw(shadow_mask).rectangle(
        (44, 28, 96, 100), fill=130
    )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(5))
    shadow = np.asarray(shadow_mask, dtype=np.float32)[..., None] / 255.0
    base = np.clip(
        base.astype(np.float32) * (1.0 - shadow * 0.45),
        0, 255,
    ).astype(np.uint8)

    styled = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(styled)
    # Three nested contour bands, a gradient fill and a bevel highlight.
    draw.rectangle((48, 32, 94, 98), outline=(10, 10, 10), width=7)
    draw.rectangle((54, 38, 88, 92), outline=(245, 210, 80), width=4)
    draw.rectangle((58, 42, 84, 88), fill=(180, 25, 35))
    for x in range(60, 83):
        t = (x - 60) / 22
        colour = (
            int(220 + 30 * t),
            int(30 + 80 * t),
            int(35 + 10 * t),
        )
        draw.line((x, 43, x, 87), fill=colour, width=1)
    draw.line((60, 44, 82, 44), fill=(255, 230, 170), width=2)
    base = np.asarray(styled).copy()
    _save(baseline, base)

    narrow = _highpass(Image.fromarray(base, "RGB"), 1.0)
    active = np.abs(narrow) >= 2.5
    candidates = {}
    for name, amount in (
        ("real_esrgan", 9),
        ("waifu2x", 7),
        ("real_cugan", 8),
        ("anime4k", 5),
    ):
        pixels = np.clip(
            base.astype(np.int16)
            + np.where(active, np.sign(narrow) * amount, 0)[..., None],
            0, 255,
        ).astype(np.uint8)
        path = tmp_path / (name + ".png")
        _save(path, pixels)
        candidates[name] = path
    return source, baseline, base, candidates


def test_single_hard_edge_is_not_classified_as_styled_effect():
    base = np.empty((128, 128, 3), dtype=np.uint8)
    base[:, :16] = (70, 70, 70)
    base[:, 16:] = (170, 170, 170)
    image = Image.fromarray(base, "RGB")
    narrow = _highpass(image, 1.0)
    wide = _highpass(image, 4.0)

    guard = _styled_effect_guard_mask(base.astype(np.float32), narrow, wide)

    assert guard.shape == (128, 128)
    assert not guard.any()


def test_soft_halo_and_dense_multi_contours_are_detected_locally(tmp_path):
    _source, baseline, _base, _candidates = _styled_fixture(tmp_path)
    with Image.open(baseline) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        narrow = _highpass(image, 1.0)
        wide = _highpass(image, 4.0)

    guard = _styled_effect_guard_mask(rgb, narrow, wide)

    assert guard.any()
    assert guard[24:108, 40:104].any()
    assert not guard[:, :10].any()


def test_fusion_automatically_preserves_styled_effects_but_keeps_plain_edge_active(tmp_path):
    source, baseline, base, candidates = _styled_fixture(tmp_path)
    original_v2 = baseline.read_bytes()
    output = tmp_path / "automatic-effect-guard.png"

    report = fuse_four_engine_details(
        source, baseline, candidates, output
    )

    with Image.open(output) as result:
        actual = np.asarray(result).copy()

    # The shadow/gradient/multi-contour headline stays exactly at accepted V2.
    np.testing.assert_array_equal(
        actual[24:108, 40:104],
        base[24:108, 40:104],
    )
    # A separate single hard contour remains eligible for bounded fusion.
    assert np.any(actual[:, 4:9] != base[:, 4:9])
    assert report["styled_effect_guard_pixels"] > 0
    assert report["automatic_styled_effect_guard"]["enabled"] is True
    assert report["automatic_styled_effect_guard"][
        "semantic_text_or_effect_classification"
    ] is False
    assert report["automatic_styled_effect_guard"]["human_review_required"] is True
    assert report["quality_certified"] is False
    assert baseline.read_bytes() == original_v2
    assert set(report["engine_pixel_effect_verified"]) == set(ENGINES)


def test_styled_effect_guard_rejects_mismatched_edge_arrays():
    with pytest.raises(ValueError, match="matching RGB and 2D edge responses"):
        _styled_effect_guard_mask(
            np.zeros((8, 8, 3), dtype=np.float32),
            np.zeros((8, 8), dtype=np.float32),
            np.zeros((8, 7), dtype=np.float32),
        )

def test_detached_halo_does_not_dilate_onto_adjacent_single_hard_edge():
    """A detached soft halo must not freeze its neighbouring single hard edge."""
    base = np.full((64, 64, 3), (90, 90, 90), dtype=np.uint8)
    narrow = np.zeros((64, 64), dtype=np.float32)
    wide = np.zeros((64, 64), dtype=np.float32)

    # One sharp vertical edge at x=32, with a broad-only response 12 px away.
    # The detached band is protected, but the adjacent hard edge stays eligible.
    narrow[:, 32] = 4.0
    wide[:, 20] = 3.0

    guard = _styled_effect_guard_mask(base.astype(np.float32), narrow, wide)

    assert guard[:, 20].all()
    assert not guard[:, 32].any()



def _layered_glyph_fixture(tmp_path):
    """Build synthetic Latin/Thai-like/CJK-like strokes with print-style effects.

    The geometry is deliberately vector-like and font-independent: this tests
    raster-risk gating, not OCR, language recognition or semantic text detection.
    """
    width, height = 240, 160
    source = tmp_path / "layered-glyph-source.png"
    baseline = tmp_path / "layered-glyph-v2.png"
    Image.new("RGB", (120, 80), (244, 244, 244)).save(
        source, format="PNG", dpi=(300, 300)
    )

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    # Latin-like diagonal glyph with a crossbar.
    draw.line((24, 132, 52, 48), fill=255, width=17)
    draw.line((52, 48, 82, 132), fill=255, width=17)
    draw.line((35, 98, 70, 98), fill=255, width=13)

    # Thai-like loop and detached upper mark/tone-mark geometry.
    draw.arc((98, 70, 145, 120), start=190, end=355, fill=255, width=11)
    draw.ellipse((124, 42, 135, 53), fill=255)
    draw.arc((117, 30, 142, 55), start=205, end=335, fill=255, width=5)

    # CJK-like orthogonal strokes, enclosure and crossing strokes.
    draw.line((164, 52, 216, 52), fill=255, width=12)
    draw.line((164, 52, 164, 132), fill=255, width=12)
    draw.line((216, 52, 216, 132), fill=255, width=12)
    draw.line((164, 92, 216, 92), fill=255, width=12)
    draw.line((190, 52, 190, 132), fill=255, width=12)

    canvas = Image.new("RGB", (width, height), (244, 244, 244))

    # Soft glow and detached drop shadow.
    glow = mask.filter(ImageFilter.GaussianBlur(8))
    glow_layer = Image.new("RGB", (width, height), (40, 120, 230))
    canvas = Image.composite(glow_layer, canvas, glow.point(lambda value: int(value * 0.35)))

    shadow = ImageChops.offset(mask, 6, 7).filter(ImageFilter.GaussianBlur(4))
    shadow_layer = Image.new("RGB", (width, height), (25, 30, 70))
    canvas = Image.composite(shadow_layer, canvas, shadow.point(lambda value: int(value * 0.70)))

    # Repeated offset extrusion plus three nested outline bands.
    for offset in range(7, 1, -1):
        extrusion = ImageChops.offset(mask, offset, offset)
        layer = Image.new("RGB", (width, height), (25, 35, 85))
        canvas = Image.composite(layer, canvas, extrusion.point(lambda value: int(value * 0.90)))

    for outline, colour in (
        (mask.filter(ImageFilter.MaxFilter(19)), (15, 20, 65)),
        (mask.filter(ImageFilter.MaxFilter(13)), (255, 190, 30)),
        (mask.filter(ImageFilter.MaxFilter(7)), (180, 25, 40)),
        (mask, (30, 160, 220)),
    ):
        layer = Image.new("RGB", (width, height), colour)
        canvas = Image.composite(layer, canvas, outline)

    # Smooth RGB gradient fill clipped to the glyph strokes.
    pixels = np.asarray(canvas).copy()
    gradient = np.zeros_like(pixels)
    for x in range(width):
        t = x / (width - 1)
        gradient[:, x, :] = (
            int(220 + 30 * t),
            int(30 + 90 * t),
            int(35 + 40 * t),
        )
    glyph = np.asarray(mask, dtype=np.uint8) > 0
    pixels[glyph] = gradient[glyph]

    styled = Image.fromarray(pixels, "RGB")
    bevel = ImageDraw.Draw(styled)
    bevel.line((31, 126, 52, 55, 74, 126), fill=(255, 240, 190), width=3)
    pixels = np.asarray(styled).copy()

    # A separate plain, single hard edge is the positive control. Clear the
    # distant glow tail so it cannot be confused with the styled-effect band.
    pixels[:, :6] = (70, 70, 70)
    pixels[:, 6:15] = (244, 244, 244)
    _save(baseline, pixels)

    narrow = _highpass(Image.fromarray(pixels, "RGB"), 1.0)
    active = np.abs(narrow) >= 2.5
    candidates = {}
    for name, amount in (
        ("real_esrgan", 9),
        ("waifu2x", 7),
        ("real_cugan", 8),
        ("anime4k", 5),
    ):
        candidate = np.clip(
            pixels.astype(np.int16)
            + np.where(active, np.sign(narrow) * amount, 0)[..., None],
            0,
            255,
        ).astype(np.uint8)
        path = tmp_path / (name + "-layered-glyph.png")
        _save(path, candidate)
        candidates[name] = path
    return source, baseline, pixels, candidates


def test_layered_latin_thai_like_and_cjk_like_effects_stay_v2_owned(tmp_path):
    """Protect multi-layer print glyphs without freezing an unrelated hard edge."""
    source, baseline, base, candidates = _layered_glyph_fixture(tmp_path)
    original_v2 = baseline.read_bytes()

    image = Image.fromarray(base, "RGB")
    narrow = _highpass(image, 1.0)
    wide = _highpass(image, 4.0)
    guard = _styled_effect_guard_mask(base.astype(np.float32), narrow, wide)

    # Each stroke family has nested contours/chromatic fill and must be guarded.
    for box in (
        (15, 35, 95, 145),   # Latin-like diagonal glyph
        (90, 25, 150, 130),  # Thai-like loop and detached upper mark
        (155, 40, 225, 140), # CJK-like orthogonal/enclosed strokes
    ):
        x1, y1, x2, y2 = box
        assert float(guard[y1:y2, x1:x2].mean()) > 0.45

    # A detached, single hard contour is not automatically classified as a
    # styled effect merely because complex artwork exists elsewhere.
    assert not guard[:, 6].any()

    output = tmp_path / "layered-glyph-fused.png"
    report = fuse_four_engine_details(source, baseline, candidates, output)
    with Image.open(output) as result:
        actual = np.asarray(result).copy()

    # Every pixel selected by the conservative effect guard stays V2-exact.
    np.testing.assert_array_equal(actual[guard], base[guard])
    # The smooth gradient inside the main diagonal stroke remains unchanged.
    np.testing.assert_array_equal(actual[80, 34:50], base[80, 34:50])
    # The unrelated plain edge remains eligible for bounded detail fusion.
    assert np.any(actual[:, 4:9] != base[:, 4:9])
    assert report["styled_effect_guard_pixels"] > 0
    assert report["automatic_styled_effect_guard"]["human_review_required"] is True
    assert report["automatic_styled_effect_guard"]["semantic_text_or_effect_classification"] is False
    assert report["quality_certified"] is False
    assert baseline.read_bytes() == original_v2
