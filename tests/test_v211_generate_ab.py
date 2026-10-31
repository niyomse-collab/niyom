"""Headless checks for same-source, same-settings V2 versus V2+HAT jobs."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.v211_generate_ab import _validate_faces, run_pair


class FakeEngine:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def selected_model_available(self, name):
        assert name == "v2_hat_assist"
        return self.available

    def process(self, source, destination, settings, *, use_ai):
        assert use_ai
        assert settings.v1_baseline
        assert settings.graphic_ai is False
        self.calls.append(settings)
        with Image.open(source) as image:
            pixels = np.asarray(image.convert("RGB").resize(
                (image.width * settings.ai_scale, image.height * settings.ai_scale),
                Image.Resampling.NEAREST
            )).copy()
        if settings.v211_photo_model == "v2_hat_assist":
            pixels[1:5, 1:5] = np.clip(
                pixels[1:5, 1:5].astype("int16") + 6, 0, 255
            ).astype("uint8")
        Image.fromarray(pixels).save(destination, dpi=(settings.dpi, settings.dpi))
        return {"model": settings.v211_photo_model}


def test_generate_pair_reuses_the_same_original_and_settings(tmp_path):
    source = tmp_path / "image.png"
    Image.new("RGB", (18, 11), (70, 80, 90)).save(source)
    engine = FakeEngine()
    out = tmp_path / "private"
    result = run_pair(
        source, out, adapter=engine, scale=2,
        faces=((.2, .1, .7, .8),)
    )
    assert [item.v211_photo_model for item in engine.calls] == [
        "real_esrgan", "v2_hat_assist"
    ]
    assert all(item.face_protection for item in engine.calls)
    assert all(item.face_regions == engine.calls[0].face_regions for item in engine.calls)
    assert all(item.dpi == 300 and item.ai_scale == 2 for item in engine.calls)
    assert result["same_pixels"] is True
    assert result["processing"]["assisted_model"] == "v2_hat_assist"
    assert result["quality_improvement_certified"] is False
    assert result["no_customer_files_uploaded"] is True
    assert (out / "V2_reference.png").is_file()
    assert (out / "V211_V2_plus_HAT.png").is_file()
    assert (out / "V2_VS_SUPER_AI.png").is_file()
    assert (out / "A_B_REPORT.json").is_file()


@pytest.mark.parametrize("bad", [
    [(0, 0, 1)],
    [(0, 0, 1, float("nan"))],
    [(-0.1, 0, 0.5, 1)],
    [(0.5, 0.5, 0.4, 0.8)],
])
def test_invalid_face_regions_rejected(bad):
    with pytest.raises(ValueError):
        _validate_faces(bad)


def test_fail_before_any_inference_when_models_are_missing(tmp_path):
    source = tmp_path / "input.png"
    Image.new("RGB", (16, 12)).save(source)
    engine = FakeEngine(available=False)
    out = tmp_path / "qa"
    with pytest.raises(RuntimeError, match="both verified model weights"):
        run_pair(source, out, adapter=engine)
    assert not out.exists()
    assert engine.calls == []


def test_quality_runner_refuses_enormous_unbounded_arrays_before_processing(tmp_path):
    source = tmp_path / "input.png"
    Image.new("RGB", (1200, 1200)).save(source)
    engine = FakeEngine()
    with pytest.raises(ValueError, match="16 megapixels"):
        run_pair(source, tmp_path / "qa", adapter=engine, scale=4)
    assert engine.calls == []
