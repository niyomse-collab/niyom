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


def test_v2_adapter_keeps_alpha_without_ai(tmp_path: Path):
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter

    src, dst = tmp_path / "input.png", tmp_path / "result.png"
    rgba = Image.new("RGBA", (16, 12), (220, 60, 30, 0))
    for x in range(4, 12):
        for y in range(3, 9):
            rgba.putpixel((x, y), (220, 60, 30, 255))
    rgba.putpixel((3, 3), (220, 60, 30, 90))
    rgba.save(src)

    adapter = NiyomSilpCoreAdapter()
    settings = EnhanceSettings()
    settings.ai_scale = 1
    adapter.process(src, dst, settings, use_ai=False)
    with Image.open(dst) as result:
        assert result.mode == "RGBA"
        assert result.getchannel("A").tobytes() == rgba.getchannel("A").tobytes()


def test_v2_adapter_keeps_alpha_with_mock_ai_2x_and_4x(tmp_path: Path):
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter

    src = tmp_path / "input.png"
    rgba = Image.new("RGBA", (12, 10), (80, 160, 220, 0))
    for x in range(3, 9):
        for y in range(2, 8):
            rgba.putpixel((x, y), (80, 160, 220, 255))
    rgba.save(src)

    class FakeEngine:
        def enhance(self, input_path, output_path, scale, **kwargs):
            with Image.open(input_path) as image:
                image.convert("RGB").resize(
                    (image.width * scale, image.height * scale)
                ).save(output_path)

        def device_name(self):
            return "test"

    adapter = NiyomSilpCoreAdapter()
    adapter.engine_manager.create_engine = lambda device: FakeEngine()
    for scale in (2, 4):
        dst = tmp_path / f"result_{scale}x.png"
        settings = EnhanceSettings()
        settings.ai_scale = scale
        adapter.process(src, dst, settings, use_ai=True)
        with Image.open(dst) as result:
            assert result.mode == "RGBA"
            assert result.size == (12 * scale, 10 * scale)
            alpha = result.getchannel("A")
            assert alpha.getpixel((0, 0)) == 0
            assert alpha.getpixel((6 * scale, 5 * scale)) == 255
