from pathlib import Path
import tempfile

import numpy as np
from PIL import Image

import pytest

from signprint_ai.processing import EnhanceSettings, print_pixels, validate_print_target
from signprint_ai.pipeline import PrintEnhancementPipeline


def test_print_pixels():
    assert print_pixels(200, 80, "cm", 150) == (11811, 4724)
    assert print_pixels(700, 40, "cm", 300) == (82677, 4724)


def test_large_vinyl_banner_300dpi_is_within_guardrail():
    target = print_pixels(700, 40, "cm", 300)
    validate_print_target(target)


def test_print_guardrail_rejects_extreme_total_pixels():
    with pytest.raises(ValueError, match="พิกเซลรวม"):
        validate_print_target(print_pixels(700, 100, "cm", 300))


def test_pipeline_without_ai():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "in.png"
        dst = td / "out.png"
        arr = np.full((80, 160, 3), (220, 190, 80), dtype=np.uint8)
        Image.fromarray(arr).save(src)
        p = PrintEnhancementPipeline()
        settings = EnhanceSettings(ai_scale=1)
        result = p.process(src, dst, settings, use_ai=False)
        assert dst.exists()
        assert result["output_size"] == (160, 80)
