"""Owner preference: three strong Windows engines, Anime4K diagnostic only."""
import numpy as np
import pytest
from PIL import Image

from tools.v211_three_engine_priority_preview import (
    PRIMARY_ENGINES, select_three_engine_preview,
)


def _write_rgb(path, rgb, *, dpi=300):
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(path, dpi=(dpi, dpi))


def _fixture(tmp_path):
    h, w = 16, 20
    yy, xx = np.mgrid[:h, :w]
    b = np.zeros((h, w, 3), dtype=np.uint8)
    b[..., 0] = 12
    b[..., 1] = 40 + xx * 7
    b[..., 2] = 100 + yy * 4
    source = tmp_path / "source.png"
    _write_rgb(source, b, dpi=300)
    baseline = tmp_path / "approved-v2.png"
    _write_rgb(baseline, b, dpi=300)
    cands = {}
    for engine, offset in [("real_esrgan", 2), ("waifu2x", 5), ("real_cugan", 1), ("anime4k", 25)]:
        p = tmp_path / (engine + ".png")
        c = b.copy()
        c[..., 0] = offset + 12
        # Anime4K flattens original green gradient in this synthetic example.
        if engine == "anime4k":
            c[..., 1] = 110
        _write_rgb(p, c, dpi=300)
        cands[engine] = p
    return source, baseline, cands


def test_three_priority_engines_only_and_anime_cannot_replace_gradient(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    original = v2.read_bytes()
    output = tmp_path / "priority-preview.png"
    result = select_three_engine_preview(src, v2, cands, output)
    assert result["selected"] == "real_cugan"
    assert result["primary_engines"] == list(PRIMARY_ENGINES)
    assert result["optional_anime4k_excluded_from_selection"] is True
    assert result["quality_certified"] is False
    assert result["preview_not_print_export"] is True
    assert v2.read_bytes() == original
    with Image.open(output) as image:
        assert image.getpixel((0, 0))[0] == 13
        assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)


def test_three_engine_preview_works_when_anime4k_fails(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    cands.pop("anime4k")
    result = select_three_engine_preview(src, v2, cands, tmp_path / "preview.png")
    assert result["selected"] == "real_cugan"


def test_large_difference_falls_back_to_identical_v2_pixels(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    for engine in PRIMARY_ENGINES:
        with Image.open(cands[engine]) as image:
            c = np.asarray(image).copy()
        c[...] = 240
        _write_rgb(cands[engine], c)
    original = v2.read_bytes()
    result = select_three_engine_preview(src, v2, cands, tmp_path / "preview.png")
    assert result["selected"] == "v2_fallback"
    with Image.open(v2) as base, Image.open(tmp_path / "preview.png") as preview:
        np.testing.assert_array_equal(np.asarray(base), np.asarray(preview))
    assert v2.read_bytes() == original


def test_never_overwrite_original_image_or_v2_reference(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    with pytest.raises(ValueError, match="cannot overwrite"):
        select_three_engine_preview(src, v2, cands, v2)
    with pytest.raises(ValueError, match="cannot overwrite"):
        select_three_engine_preview(src, v2, cands, src)


def test_reject_missing_priority_engine(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    cands.pop("waifu2x")
    with pytest.raises(ValueError, match="three priority"):
        select_three_engine_preview(src, v2, cands, tmp_path / "out.png")


def test_reject_rgba_candidate_that_changes_alpha(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    for p in [src, v2, *cands.values()]:
        with Image.open(p) as image:
            rgb = np.asarray(image.convert("RGB"))
        alpha = np.full(rgb.shape[:2], 125, dtype=np.uint8)
        rgba = np.dstack([rgb, alpha])
        Image.fromarray(rgba, "RGBA").save(p)
    with Image.open(cands["real_esrgan"]) as image:
        a = np.asarray(image).copy()
    a[0, 0, 3] = 0
    Image.fromarray(a, "RGBA").save(cands["real_esrgan"])
    with pytest.raises(ValueError, match="alpha|transparency|RGBA"):
        select_three_engine_preview(src, v2, cands, tmp_path / "preview.png")
