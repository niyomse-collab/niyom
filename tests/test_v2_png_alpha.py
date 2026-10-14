"""Regression coverage for transparent PNG processing in v2."""
from pathlib import Path

import numpy as np
from PIL import Image

from signprint_ai.processing import EnhanceSettings, load_image
from signprint_ai.pipeline import PrintEnhancementPipeline


def test_transparent_png_roundtrip_without_ai(tmp_path: Path):
    source = tmp_path / "source.png"
    target = tmp_path / "output.png"
    pixels = np.zeros((24, 32, 4), dtype=np.uint8)
    pixels[..., :3] = (210, 40, 70)
    pixels[5:19, 6:26, 3] = 255
    pixels[4, 5, 3] = 128
    Image.fromarray(pixels, "RGBA").save(source)

    rgb, alpha = load_image(source)
    assert alpha is not None
    assert alpha[0, 0] == 0
    assert alpha[10, 10] == 255

    settings = EnhanceSettings()
    settings.ai_scale = 1
    settings.color_mode = "RGB"
    PrintEnhancementPipeline().process(source, target, settings, use_ai=False)
    with Image.open(target) as output:
        assert output.mode == "RGBA"
        assert output.getchannel("A").getpixel((0, 0)) == 0
        assert output.getchannel("A").getpixel((10, 10)) == 255
        assert output.getchannel("A").getpixel((5, 4)) == 128
