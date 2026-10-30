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


def test_direct_hat_export_rejects_cmyk_icc_before_inference(tmp_path):
    """Never attach a CMYK source ICC to the RGB output of the HAT model."""
    source = tmp_path / "source_cmyk.tiff"
    target = tmp_path / "invalid_rgb_with_cmyk_icc.tiff"
    Image.new("CMYK", (3, 3), (10, 20, 30, 40)).save(
        source, icc_profile=b"cmyk-source-profile"
    )
    engine = fake_engine()
    engine.enhance_tile = lambda *args, **kwargs: pytest.fail(
        "CMYK colour preflight must run before AI inference"
    )
    with pytest.raises(ValueError, match="CMYK"):
        engine.enhance(source, target, scale=2)
    assert not target.exists()


def test_direct_hat_alpha_to_jpeg_rejects_before_inference(tmp_path):
    source = tmp_path / "alpha.png"
    target = tmp_path / "flattened.jpg"
    Image.new("RGBA", (3, 3), (255, 0, 0, 128)).save(source)
    engine = fake_engine()
    engine.enhance_tile = lambda *args, **kwargs: pytest.fail(
        "Alpha/JPEG preflight must run before AI inference"
    )
    with pytest.raises(ValueError, match="PNG/TIFF"):
        engine.enhance(source, target, scale=2)
    assert not target.exists()


def test_direct_hat_failed_encoder_preserves_previous_output(tmp_path, monkeypatch):
    """A failed save must not corrupt an existing print file or leak temp files."""
    source = tmp_path / "input.png"
    target = tmp_path / "output.png"
    Image.new("RGB", (3, 3), (200, 40, 20)).save(source)
    Image.new("RGB", (6, 6), (10, 20, 30)).save(target)
    previous = target.read_bytes()
    real_save = Image.Image.save

    def fail_after_partial_write(self, fp, *args, **kwargs):
        # Source and destination are already created before the monkeypatch.
        fp = str(fp)
        if fp != str(source) and fp != str(target):
            from pathlib import Path
            Path(fp).write_bytes(b"partial PNG, simulated disk full")
            raise OSError("simulated disk full")
        return real_save(self, fp, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail_after_partial_write)
    with pytest.raises(OSError, match="simulated disk full"):
        fake_engine().enhance(source, target, scale=2)
    assert target.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {source, target}


def test_direct_hat_successful_atomic_export_replaces_previous_output(tmp_path):
    source = tmp_path / "input.png"
    target = tmp_path / "output.png"
    Image.new("RGB", (3, 3), (220, 30, 10)).save(source)
    Image.new("RGB", (6, 6), (10, 20, 30)).save(target)
    fake_engine().enhance(source, target, scale=2)
    with Image.open(target) as result:
        assert result.size == (6, 6)
        assert result.getpixel((0, 0)) == (220, 30, 10)
    assert set(tmp_path.iterdir()) == {source, target}
