"""V2.1.1 multi-model contract: HAT augments V2, never replaces its output."""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from signprint_ai.v211_hat_assist import HATAssistEngine, blend_v2_with_hat


def contrasts():
    rgb = np.full((64, 64, 3), 35, dtype=np.uint8)
    rgb[:, 32:] = 215
    brighter = np.full_like(rgb, 4)
    brighter[:, 32:] = 249
    return rgb, brighter


def test_hat_assist_makes_bounded_real_edge_change():
    original, hat = contrasts()
    output = blend_v2_with_hat(original, hat)
    assert not np.array_equal(output, original)
    assert np.max(np.abs(output.astype("int16") - original.astype("int16"))) <= 38
    # A plain area stays V2 rather than inheriting the overall HAT tint.
    np.testing.assert_array_equal(output[2:10, 2:10], original[2:10, 2:10])


def test_guarded_face_pixels_are_identical_to_v2_baseline():
    original, hat = contrasts()
    protected = ((0.28, 0.2, 0.70, 0.8),)
    output = blend_v2_with_hat(original, hat, protected_regions=protected)
    np.testing.assert_array_equal(output[18:47, 20:44], original[18:47, 20:44])
    assert not np.array_equal(output[:12, 27:37], original[:12, 27:37])


def test_strength_zero_and_matching_models_preserve_all_v2_pixels():
    original, hat = contrasts()
    np.testing.assert_array_equal(
        blend_v2_with_hat(original, hat, strength=0), original
    )
    np.testing.assert_array_equal(
        blend_v2_with_hat(original, original, strength=1), original
    )


def test_blend_checks_geometry_and_invalid_faces():
    original, hat = contrasts()
    with pytest.raises(ValueError):
        blend_v2_with_hat(original, hat[:32])
    with pytest.raises(ValueError):
        blend_v2_with_hat(original, hat, strength=2)
    with pytest.raises(ValueError):
        blend_v2_with_hat(original, hat, protected_regions=((0, 0, float("nan"), 1),))


class DummyEngine:
    def __init__(self, name, log):
        self.name, self.log = name, log
        self.upsampler = SimpleNamespace(tile_size=96 if name == "hat" else 256, tile_pad=32)
    def device_name(self):
        return "CPU"
    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        self.log.append((self.name, pixels.copy()))
        base = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        if self.name == "hat":
            base = np.clip(base.astype(np.int16) * 1.10, 0, 255).astype(np.uint8)
        return base
    def enhance(self, src, dst, scale=4, progress_callback=None, cancel_check=None):
        self.log.append((self.name, str(src)))
        with Image.open(src) as im:
            output = np.repeat(np.repeat(np.asarray(im.convert("RGB")), scale, axis=0), scale, axis=1)
        if self.name == "hat":
            output = np.clip(output.astype(np.int16) * 1.10, 0, 255).astype(np.uint8)
        Image.fromarray(output).save(dst)
        if progress_callback:
            progress_callback(100)
        return {"device": "CPU"}


def test_both_engines_run_on_the_same_source_tile():
    log = []
    original, _ = contrasts()
    engine = HATAssistEngine(DummyEngine("v2", log), DummyEngine("hat", log))
    result = engine.enhance_tile(original, scale=2)
    assert result.shape == (128, 128, 3)
    assert engine.upsampler.tile_size == 96
    assert [n for n, _ in log] == ["v2", "hat"]
    np.testing.assert_array_equal(log[0][1], log[1][1])


def test_combined_engine_writes_image_and_preserves_call_order(tmp_path):
    log = []
    source, destination = tmp_path / "source.png", tmp_path / "result.png"
    original, _ = contrasts()
    Image.fromarray(original).save(source)
    engine = HATAssistEngine(DummyEngine("v2", log), DummyEngine("hat", log))
    details = engine.enhance(source, destination, scale=2)
    assert destination.exists()
    assert [n for n, _ in log] == ["v2", "hat"]
    assert log[0][1] == log[1][1] == str(source)
    assert details["hat_assist"] is True
    assert details["output_size"] == (128, 128)


def test_adapter_routes_v2_first_and_hat_after(monkeypatch):
    from signprint_ai import v211_hat_engine
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    calls = []
    selected = SimpleNamespace(name="CPU", backend="CPU", device_id="cpu")
    class FakeV2(DummyEngine):
        def __init__(self):
            super().__init__("v2", [])
            self.selected = selected
    def new_v2(device):
        calls.append("v2")
        return FakeV2()
    class FakeHAT(DummyEngine):
        def __init__(self, selected):
            calls.append("hat")
            super().__init__("hat", [])
    monkeypatch.setattr(v211_hat_engine, "HATModelEngine", FakeHAT)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        create_engine=new_v2,
        device_manager=SimpleNamespace(get_default_device=lambda: selected),
        engine=None,
    )
    settings = SimpleNamespace(v211_photo_model="v2_hat_assist",
                               v211_hat_assist_strength=.85,
                               device="AUTO", graphic_ai=False,
                               text_graphic_boost=0,
                               face_protection=False, face_regions=None)
    engine = adapter.create_job_engine(settings)
    assert isinstance(engine, HATAssistEngine)
    assert calls == ["v2", "hat"]
