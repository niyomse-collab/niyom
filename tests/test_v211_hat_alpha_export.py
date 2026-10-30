"""V2.1.1 direct HAT export must retain source transparency and metadata.

These are deterministic export regressions; the stub is NOT real HAT inference.
"""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from signprint_ai.v211_hat_engine import HATModelEngine


def fake_engine():
    engine = object.__new__(HATModelEngine)
    engine.selected = SimpleNamespace(name="QA-stub")
    engine.upsampler = SimpleNamespace(tile_size=2, tile_pad=1)
    engine.enhance_tile = lambda pixels, scale, cancel_check=None: np.repeat(
        np.repeat(pixels, scale, axis=0), scale, axis=1
    )
    return engine


@pytest.mark.parametrize("extension", [".png", ".tiff"])
def test_direct_hat_export_retains_rgba_icc_and_dpi(tmp_path, extension):
    source = tmp_path / "source.png"
    target = tmp_path / ("result" + extension)
    pixels = np.zeros((5, 6, 4), dtype=np.uint8)
    pixels[:, :, :3] = 0  # adversarial hidden black RGB
    pixels[1:4, 1:5, :3] = (225, 40, 30)
    pixels[1:4, 1:5, 3] = 255
    Image.fromarray(pixels, "RGBA").save(
        source, dpi=(300, 300), icc_profile=b"qa-icc-profile"
    )
    info = fake_engine().enhance(source, target, scale=4)
    assert info["output_size"] == (24, 20)
    with Image.open(target) as result:
        assert result.mode == "RGBA"
        assert result.size == (24, 20)
        assert result.getchannel("A").getextrema() == (0, 255)
        assert result.info.get("icc_profile") == b"qa-icc-profile"
        assert all(abs(v - 300) < 1 for v in result.info["dpi"])
        # Transparent-edge RGB should not stay black next to red artwork.
        assert result.getpixel((0, 4))[0] > 0


def test_direct_hat_export_rejects_alpha_to_jpeg(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGBA", (3, 3), (255, 0, 0, 128)).save(source)
    target = tmp_path / "flattened.jpg"
    with pytest.raises(ValueError, match="PNG/TIFF"):
        fake_engine().enhance(source, target, scale=2)
    assert not target.exists()
