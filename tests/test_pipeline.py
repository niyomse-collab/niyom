from pathlib import Path
import tempfile

import numpy as np
from PIL import Image

from signprint_ai.processing import EnhanceSettings, print_pixels
from signprint_ai.pipeline import PrintEnhancementPipeline


def test_print_pixels():
    assert print_pixels(200, 80, "cm", 150) == (11811, 4724)


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
