"""V2.1 synthetic QA: no dark/coloured halos when resizing transparent vinyl art.

The legacy EnhanceSettings route is deliberately isolated. No customer files
or private ICC profiles are committed.
"""
import numpy as np
import pytest
from PIL import Image

from signprint_ai import large_image
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.processing import EnhanceSettings
from signprint_ai.v21_graphics_ai import V21Settings


def _source(path):
    pixels = np.zeros((32, 48, 4), dtype=np.uint8)
    # Deliberately dark hidden RGB under fully transparent ink.
    pixels[:, :, :3] = (0, 0, 0)
    pixels[6:26, 9:39, :3] = (240, 110, 35)
    pixels[6:26, 9:39, 3] = 255
    pixels[9:23, 9, 3] = 150
    Image.fromarray(pixels, "RGBA").save(path)
    return pixels


@pytest.mark.parametrize("mode", ["stretch", "fit"])
def test_v21_streamed_cutout_resize_preserves_ink_edge_colour(
    tmp_path, monkeypatch, mode
):
    # Force disk tiles without needing the GPU.  The bug affected final
    # resizing, not AI inference, so 1x validates the actual export path.
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    source = tmp_path / "cutout.png"
    _source(source)
    destination = tmp_path / "resized.png"
    settings = V21Settings(
        ai_scale=1, color_mode="RGB", resize_mode=mode,
        print_width=144 / 300, print_height=144 / 300,
        print_unit="inch", dpi=300,
    )
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    info = adapter.process(source, destination, settings, use_ai=False)
    assert info["processing_mode"] == "disk_tiles"
    with Image.open(destination) as output:
        assert output.mode == "RGBA" and output.size == (144, 144)
        rgba = np.asarray(output)
    alpha = rgba[..., 3]
    assert alpha[0, 0] == 0
    assert alpha.max() == 255
    partial = (alpha >= 45) & (alpha <= 210)
    assert np.count_nonzero(partial) > 10
    # For uniform-colour ink, partial coverage must change opacity, NOT RGB.
    colour_error = np.abs(
        rgba[..., :3][partial].astype(np.int16)
        - np.array([240, 110, 35], dtype=np.int16)
    )
    assert np.percentile(colour_error.max(axis=1), 95) <= 12


def test_v21_direct_source_alpha_is_not_double_resampled(tmp_path):
    source = tmp_path / "cutout.png"
    _source(source)
    destination = tmp_path / "test.png"
    settings = V21Settings(resize_mode="stretch", color_mode="RGB")
    original = large_image.open_vips(source, access="random")
    alpha = original.extract_band(original.bands - 1).cast("uchar")
    expected_alpha = large_image.resize_image(
        alpha, (137, 91), "stretch", background=[0]
    ).write_to_memory()
    rgb = large_image.as_rgb(original)
    result = large_image.prepare_v21_alpha_safe_resize(
        rgb, source, (137, 91), settings, destination
    )
    assert result.hasalpha()
    actual_alpha = result.extract_band(3).write_to_memory()
    assert actual_alpha == expected_alpha


def test_v21_cmyk_pretransform_is_white_matted_at_alpha_zero(tmp_path):
    source = tmp_path / "cutout.png"
    _source(source)
    settings = V21Settings(resize_mode="stretch", color_mode="CMYK")
    image = large_image.as_rgb(large_image.open_vips(source))
    ready = large_image.prepare_v21_alpha_safe_resize(
        image, source, (144, 96), settings, tmp_path / "output.tif"
    )
    assert not ready.hasalpha()
    pixels = np.asarray(large_image.to_pillow(ready))
    np.testing.assert_array_equal(pixels[0, 0], [255, 255, 255])
    assert pixels[48, 72, 0] >= 238


def test_legacy_v2_settings_do_not_enable_v21_resize():
    assert not hasattr(EnhanceSettings(), "v21_alpha_safe_resize")
    assert V21Settings().v21_alpha_safe_resize is True
