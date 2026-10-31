"""V2.1.1 SwinIR first-stage contract; no weight download in unit tests."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from signprint_ai.v211_swinir_preprocess import (
    SWINIR_BYTES, SWINIR_SHA256, _pad_shape,
    verify_swinir_checkpoint, blend_pre_restoration,
    PreRestoreV2Engine,
)


def test_pinned_upstream_checkpoint_fails_closed(tmp_path):
    assert len(SWINIR_SHA256) == 64 and SWINIR_BYTES > 1_000_000
    with pytest.raises(FileNotFoundError):
        verify_swinir_checkpoint(tmp_path / "absent.pth")
    fake = tmp_path / "fake.pth"
    fake.write_bytes(b"not a real SwinIR model")
    with pytest.raises(RuntimeError, match="checkpoint"):
        verify_swinir_checkpoint(fake)


@pytest.mark.parametrize("h,w", [(1, 1), (7, 23), (24, 24), (31, 37), (63, 64)])
def test_swinir_window_safe_padding(h, w):
    b, r, mode = _pad_shape(h, w)
    assert (h + b) % 8 == 0
    assert (w + r) % 8 == 0
    assert mode in ("reflect", "replicate")
    if mode == "reflect":
        assert b < h and r < w


def test_color_fills_and_typography_boundaries_preserved():
    src = np.empty((64, 64, 3), dtype=np.uint8)
    src[:] = (248, 22, 35)
    src[:, 32:] = (18, 65, 247)
    result = blend_pre_restoration(src, np.full_like(src, 90))
    np.testing.assert_array_equal(result, src)


def test_photographic_noise_can_be_reduced_before_v2_without_texture_injection():
    rng = np.random.default_rng(211)
    src = np.clip(
        120 + rng.integers(-8, 9, size=(96, 96, 1)),
        0, 255
    ).astype("uint8")
    src = np.repeat(src, 3, axis=2)
    clean = cv2.GaussianBlur(src, (5, 5), .75)
    out = blend_pre_restoration(src, clean, strength=.8)
    assert out.shape == src.shape
    assert out.dtype == np.uint8
    assert np.any(out != src)
    assert float(out.std()) < float(src.std())
    assert np.max(np.abs(out.astype("int16") - src.astype("int16"))) <= 24


def test_selected_face_region_is_pixel_identical():
    rng = np.random.default_rng(7)
    src = (120 + rng.integers(-8, 9, size=(96, 96, 3))).astype("uint8")
    clean = np.full_like(src, 120)
    out = blend_pre_restoration(
        src, clean, .9, protected_regions=((.20, .20, .80, .80),)
    )
    np.testing.assert_array_equal(out[20:76, 20:76], src[20:76, 20:76])


@pytest.mark.parametrize("bad", [-1, 1.01, float("nan"), float("inf")])
def test_invalid_pre_restore_strength_rejected(bad):
    source = np.zeros((16, 16, 3), dtype="uint8")
    with pytest.raises(ValueError):
        blend_pre_restoration(source, source, bad)


class DummyV2:
    def __init__(self, log):
        self.log = log
        self.upsampler = SimpleNamespace(tile_size=128, tile_pad=12)
        self.selected = SimpleNamespace(device_id="cpu", name="CPU", backend="CPU")
    def device_name(self):
        return "CPU"
    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        self.log.append(("v2", pixels.copy()))
        return np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
    def enhance(self, src, dst, scale=2, progress_callback=None, cancel_check=None):
        with Image.open(src) as img:
            pixels = np.asarray(img.convert("RGB")).copy()
        self.log.append(("v2_file", pixels))
        Image.fromarray(
            np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        ).save(dst)
        return {"model": "RealESRGAN_x4plus"}


class DummySwinIR:
    def __init__(self, log):
        self.log = log
        self.upsampler = SimpleNamespace(tile_size=48, tile_pad=16)
    def denoise_tile(self, pixels, cancel_check=None):
        self.log.append(("swinir", pixels.copy()))
        return cv2.GaussianBlur(pixels, (5, 5), .75)


def _noisy_photo(seed=10):
    rng = np.random.default_rng(seed)
    pixels = np.clip(118 + rng.integers(-9, 10, (72, 80, 1)), 0, 255).astype("uint8")
    return np.repeat(pixels, 3, axis=2)


def test_swinir_works_before_v2_in_same_tile():
    log = []
    v2 = DummyV2(log)
    pre = PreRestoreV2Engine(v2, DummySwinIR(log), strength=.85)
    pixels = _noisy_photo()
    out = pre.enhance_tile(pixels, scale=2)
    assert out.shape == (144, 160, 3)
    assert [name for name, _ in log] == ["swinir", "v2"]
    assert pre.next_pass_engine() is v2
    assert pre.upsampler.tile_size == 48
    np.testing.assert_array_equal(out[::2, ::2], log[1][1])


def test_file_path_pre_restoration_runs_before_v2_and_preserves_face_roi(tmp_path):
    log = []
    source, target = tmp_path / "source.png", tmp_path / "output.png"
    pixels = _noisy_photo()
    Image.fromarray(pixels).save(source)
    pre = PreRestoreV2Engine(
        DummyV2(log), DummySwinIR(log), strength=.8,
        protected_regions=((.2, .2, .7, .7),),
    )
    pre.enhance(source, target, scale=2)
    assert target.is_file()
    assert [v[0] for v in log][-1] == "v2_file"
    actual_source_to_v2 = log[-1][1]
    assert actual_source_to_v2.shape == pixels.shape
    # Source regions remain unchanged on the 1x pre-restoration pass.
    np.testing.assert_array_equal(
        actual_source_to_v2[20:46, 20:54],
        pixels[20:46, 20:54]
    )


def test_adapter_can_select_swinir_as_preprocessor_without_replacing_v2(monkeypatch):
    from signprint_ai import v211_swinir_preprocess
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter

    log = []
    base = DummyV2(log)

    class FakeSwinIR(DummySwinIR):
        def __init__(self, selected):
            assert selected is base.selected
            super().__init__(log)

    monkeypatch.setattr(v211_swinir_preprocess, "SwinIRColorDenoiser", FakeSwinIR)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(create_engine=lambda _: base)
    settings = SimpleNamespace(
        v211_photo_model="v2_swinir_pre", device="AUTO",
        graphic_ai=False, text_graphic_boost=0, face_regions=None,
        face_protection=False, v211_swinir_pre_strength=.7
    )
    engine = adapter.create_job_engine(settings)
    assert isinstance(engine, PreRestoreV2Engine)
    assert engine.v2 is base
    assert engine.next_pass_engine() is base


def test_8x_second_pass_skips_duplicate_restoration():
    import inspect
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.large_image import _large_job
    assert "engine.next_pass_engine()" in inspect.getsource(NiyomSilpCoreAdapter.process)
    assert "engine.next_pass_engine()" in inspect.getsource(_large_job)



def test_partial_face_roi_on_large_tile_is_clipped_and_preserved():
    log = []
    pixels = _noisy_photo()
    engine = PreRestoreV2Engine(
        DummyV2(log), DummySwinIR(log), strength=.9,
    )
    engine.enhance_graphic_tile(
        pixels, scale=2, cancel=None,
        protected_regions=((-0.2, -0.2, .6, .6),)
    )
    sent_to_v2 = log[-1][1]
    np.testing.assert_array_equal(sent_to_v2[:40, :40], pixels[:40, :40])


def test_swinir_preflight_requires_both_separate_weights(tmp_path, monkeypatch):
    from signprint_ai import v211_swinir_preprocess, niyomsil_core_adapter
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    sw = tmp_path / "noise15.pth"
    v2 = tmp_path / "esrgan.pth"
    monkeypatch.setattr(v211_swinir_preprocess, "swinir_checkpoint_path", lambda: sw)
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: v2)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("v2_swinir_pre") is False
    sw.write_bytes(b"research stub only")
    assert adapter.selected_model_available("v2_swinir_pre") is False
    v2.write_bytes(b"research stub only")
    assert adapter.selected_model_available("v2_swinir_pre") is True


def test_swinir_desktop_mode_selected_not_replacing_v2():
    import inspect
    from signprint_ai.app_v2 import App
    ui = inspect.getsource(App._settings)
    start = inspect.getsource(App.start_processing)
    assert '"v2_swinir_pre"' in ui
    assert '"v2_swinir_pre"' in start



def test_sigma15_noise_is_not_misclassified_as_a_wall_of_typographic_edges():
    rng = np.random.default_rng(20261031)
    clean = np.full((96, 96, 3), 128, dtype=np.uint8)
    noisy = np.clip(
        clean.astype("float32") + rng.normal(0, 15, clean.shape),
        0, 255
    ).astype("uint8")
    restored = blend_pre_restoration(noisy, clean, strength=.8)
    before_error = np.mean((noisy.astype("float32") - clean)**2)
    after_error = np.mean((restored.astype("float32") - clean)**2)
    assert after_error < before_error * .65, (
        "Noisy photo falsely classified as all edges; source restoration ineffective"
    )
