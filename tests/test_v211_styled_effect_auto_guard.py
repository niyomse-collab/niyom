"""Automatic styled-effect risk guard regressions.

All rasters here are synthetic. These tests verify conservative pixel gating,
not semantic text detection, native inference, or print quality.
"""
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

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
    base[:, :16] = (70, 70, 70)
    base[:, 16:] = (170, 170, 170)

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
    assert not guard[:, 8:22].any()


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
    assert np.any(actual[:, 14:19] != base[:, 14:19])
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
    with pytest.raises(ValueError, match="matching 2D edge responses"):
        _styled_effect_guard_mask(
            np.zeros((8, 8, 3), dtype=np.float32),
            np.zeros((8, 8), dtype=np.float32),
            np.zeros((8, 7), dtype=np.float32),
        )
