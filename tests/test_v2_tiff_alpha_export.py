"""Regression for V2 RGBA delivery from both memory and disk-backed paths.

Transparent files are synthesized. Do not put customer artworks in public git.
"""
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from signprint_ai import large_image
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.processing import EnhanceSettings


def transparent_master(path):
    pixels = np.zeros((36, 48, 4), dtype=np.uint8)
    # Fully transparent RGB deliberately contains dark hidden colours.
    pixels[:, :, :3] = (15, 28, 55)
    pixels[7:30, 9:40, :3] = (220, 55, 18)
    pixels[7:30, 9:40, 3] = 255
    pixels[10:26, 13:36, 3] = 128
    Image.fromarray(pixels, "RGBA").save(path)
    return pixels


@pytest.mark.parametrize("streaming", [False, True], ids=["memory", "disk_tiles"])
@pytest.mark.parametrize("extension", ["png", "tif"])
@pytest.mark.parametrize("mode", ["fit", "stretch"])
def test_rgb_export_retains_alpha(streaming, extension, mode, tmp_path, monkeypatch):
    # No AI model is required: isolate the alpha/export path.
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1 if streaming else 10**9)
    src = tmp_path / "master.png"
    transparent_master(src)
    dst = tmp_path / ("enhanced." + extension)
    settings = EnhanceSettings(ai_scale=1, color_mode="RGB", resize_mode=mode,
        print_width=144/300, print_height=108/300, print_unit="inch", dpi=300)
    output = NiyomSilpCoreAdapter().process(src, dst, settings, use_ai=False)
    assert output["processing_mode"] == ("disk_tiles" if streaming else "memory")
    with Image.open(dst) as im:
        assert im.mode == "RGBA", (extension, streaming, im.mode)
        assert im.size == (144, 108)
        a = np.asarray(im.getchannel("A"))
        assert a[0, 0] == 0
        assert a[54, 72] > 0
        assert np.any((a > 0) & (a < 255))
        if mode == "fit":
            assert a[0, 70] == 0
        if extension == "tif":
            assert im.info["dpi"] == pytest.approx((300, 300), abs=.05)


@pytest.mark.parametrize("streaming", [False, True], ids=["memory", "disk_tiles"])
@pytest.mark.parametrize("extension", ["jpg", "pdf"])
def test_opaque_exports_compose_white_instead_of_black(streaming, extension, tmp_path, monkeypatch):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1 if streaming else 10**9)
    src = tmp_path / "master.png"
    transparent_master(src)
    dst = tmp_path / ("output." + extension)
    settings = EnhanceSettings(ai_scale=1, color_mode="RGB", resize_mode="stretch",
        print_width=96/300, print_height=72/300, print_unit="inch", dpi=300)
    NiyomSilpCoreAdapter().process(src, dst, settings, use_ai=False)
    if extension == "pdf":
        from pypdf import PdfReader
        im = PdfReader(dst).pages[0].images[0].image.convert("RGB")
    else:
        im = Image.open(dst).convert("RGB")
    # At source top-left alpha is zero despite hidden RGB = (15, 28, 55).
    pixel = im.getpixel((2, 2))
    assert min(pixel) >= 246, (extension, streaming, pixel)


def test_alpha_export_change_does_not_change_v2_slider_settings():
    # V2 remains responsible for connecting the four real processing controls;
    # contrast and saturation UI fields must also survive API construction.
    values = dict(denoise=18, flat_smoothing=18, text_graphic_boost=28,
        sharpness=26, contrast=8, saturation=0)
    opts = EnhanceSettings(**values)
    assert all(getattr(opts, key) == value for key, value in values.items())
    for key in ("denoise", "flat_smoothing", "text_graphic_boost", "sharpness"):
        assert getattr(replace(opts, **{key: 0}), key) == 0
