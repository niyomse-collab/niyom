"""V2.1.1 HAT direct-export EXIF orientation regression.

The existing V2 core already rotates EXIF-tagged phone photos; experimental
HAT must preserve the same geometry and keep transparency aligned.
"""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageOps

from signprint_ai.v211_hat_engine import HATModelEngine


def stub():
    engine = object.__new__(HATModelEngine)
    engine.selected = SimpleNamespace(name="QA stub")
    engine.upsampler = SimpleNamespace(tile_size=4, tile_pad=1)
    engine.enhance_tile = lambda pixels, scale, cancel_check=None: np.repeat(
        np.repeat(pixels, scale, axis=0), scale, axis=1
    )
    return engine


@pytest.mark.parametrize("orientation", [3, 6, 8])
def test_hat_phone_photo_exif_orientation(tmp_path, orientation):
    source, target = tmp_path / "phone.png", tmp_path / "render.png"
    pixels = np.zeros((3, 2, 3), dtype=np.uint8)
    pixels[0, 0] = (250, 0, 0)
    pixels[0, 1] = (0, 250, 0)
    pixels[2, 0] = (0, 0, 250)
    pixels[2, 1] = (245, 240, 15)
    exif = Image.Exif()
    exif[274] = orientation
    Image.fromarray(pixels, "RGB").save(source, exif=exif)
    result = stub().enhance(source, target, scale=2)
    with Image.open(source) as original:
        expected = ImageOps.exif_transpose(original)
        expected = expected.resize((expected.width * 2, expected.height * 2),
                                   Image.Resampling.NEAREST)
    with Image.open(target) as actual:
        assert actual.size == expected.size == result["output_size"]
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))
        # Output pixels are physically rotated; no EXIF re-rotation on open.
        assert actual.getexif().get(274, 1) == 1


def test_hat_rgba_orientation_keeps_alpha_on_same_pixel(tmp_path):
    source, target = tmp_path / "alpha.png", tmp_path / "alpha-output.png"
    pixels = np.zeros((3, 2, 4), dtype=np.uint8)
    pixels[:, :, :3] = (200, 80, 40)
    pixels[0, 0, 3] = 255
    exif = Image.Exif()
    exif[274] = 6
    Image.fromarray(pixels, "RGBA").save(source, exif=exif)
    stub().enhance(source, target, scale=2)
    with Image.open(target) as output:
        assert output.size == (6, 4)
        a = np.asarray(output.getchannel("A"))
        assert a.max() == 255
        # Orientation=6 sends top-left source to the top-right output.
        assert a[:2, -2:].max() == 255
        assert a[-2:, :2].max() < 10  # Lanczos can introduce minor ringing
