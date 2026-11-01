"""8x HAT Assist may enhance only the original source, not an intermediate.

These are pipeline-routing regressions with deterministic fake engines. They
do NOT certify image quality or exercise real checkpoint inference.
"""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v21_graphics_ai import V21Settings
from signprint_ai.v211_hat_assist import HATAssistEngine


class RecordingEngine:
    def __init__(self, name, log):
        self.name = name
        self.log = log
        self.upsampler = SimpleNamespace(
            tile_size=96 if name == "hat" else 256,
            tile_pad=32 if name == "hat" else 16,
        )

    def device_name(self):
        return "CPU"

    def enhance(self, src, dst, scale=4, progress_callback=None,
                cancel_check=None):
        with Image.open(src) as im:
            source_size = im.size
            pixels = np.asarray(im.convert("RGB"))
        self.log.append((self.name, scale, source_size))
        result = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        Image.fromarray(result, "RGB").save(dst)
        if progress_callback:
            progress_callback(100)
        return {"model": self.name}

    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        self.log.append((self.name, scale, (pixels.shape[1], pixels.shape[0])))
        return np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)


def test_8x_second_pass_is_approved_v2_not_hat():
    log = []
    v2 = RecordingEngine("v2", log)
    hat = RecordingEngine("hat", log)
    assist = HATAssistEngine(v2, hat)
    assert assist.next_pass_engine() is v2
    # Mirror disk tile routing: 4x V2+HAT, then V2-only 2x.
    source = np.zeros((24, 32, 3), dtype=np.uint8)
    source[:, 16:] = (230, 20, 40)
    first = assist.enhance_tile(source, scale=4)
    second = assist.next_pass_engine().enhance_tile(first, scale=2)
    assert second.shape == (192, 256, 3)
    assert log == [
        ("v2", 4, (32, 24)),
        ("hat", 4, (32, 24)),
        ("v2", 2, (128, 96)),
    ]


def test_second_pass_unwraps_experimental_graphic_wrapper():
    v2 = RecordingEngine("v2", [])
    wrapper = SimpleNamespace(
        photo=v2,
        upsampler=SimpleNamespace(tile_size=128, tile_pad=16),
    )
    assist = HATAssistEngine(wrapper, RecordingEngine("hat", []))
    assert assist.next_pass_engine() is v2


def test_real_memory_adapter_8x_uses_hat_on_original_once(tmp_path):
    log = []
    v2 = RecordingEngine("v2", log)
    hat = RecordingEngine("hat", log)
    combined = HATAssistEngine(v2, hat)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.create_job_engine = lambda settings: combined
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(
                device_id="cpu", name="CPU",
            )
        ),
    )
    source = tmp_path / "source.png"
    output = tmp_path / "enhanced.png"
    pixels = np.zeros((32, 32, 3), dtype=np.uint8)
    pixels[8:24, 8:24] = (220, 20, 80)
    Image.fromarray(pixels, "RGB").save(source)
    settings = V21Settings(
        ai_scale=8, device="CPU", face_protection=False,
        resize_mode="stretch", v211_photo_model="v2_hat_assist",
        v21_precision_ink=False, graphic_ai=False,
    )
    result = adapter.process(source, output, settings, use_ai=True)
    assert result["ai_scale"] == 8
    with Image.open(output) as verified:
        assert verified.size == (256, 256)
    assert log == [
        ("v2", 4, (32, 32)),
        ("hat", 4, (32, 32)),
        ("v2", 2, (128, 128)),
    ]


@pytest.mark.parametrize("ink_rgb", [(180, 40, 70), (20, 175, 235), (245, 230, 35)])
def test_8x_memory_rgba_keeps_transparent_cutout_and_single_hat_source(tmp_path, ink_rgb):
    """Regression: 8x print cutouts must not acquire an opaque background.

    Deterministic routing/alpha test only; real neural quality remains unproven.
    """
    log = []
    v2 = RecordingEngine("v2", log)
    hat = RecordingEngine("hat", log)
    combined = HATAssistEngine(v2, hat)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.create_job_engine = lambda settings: combined
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(
                device_id="cpu", name="CPU",
            )
        ),
    )
    source = tmp_path / "cutout.png"
    output = tmp_path / "cutout_8x.png"
    pixels = np.zeros((32, 32, 4), dtype=np.uint8)
    pixels[:, :, :3] = ink_rgb
    pixels[5:27, 5:27, 3] = 255
    # Keep an opaque plateau well away from both alpha boundaries. Lanczos
    # resampling legitimately changes coverage near a contour; sampling there
    # would confuse edge antialiasing with a lost opaque interior.
    # Semi-transparent ink must remain semi-transparent after both passes.
    pixels[11:21, 11:21, 3] = 128
    Image.fromarray(pixels, "RGBA").save(source)
    settings = V21Settings(
        ai_scale=8, device="CPU", face_protection=False,
        resize_mode="stretch", v211_photo_model="v2_hat_assist",
        v21_precision_ink=False, graphic_ai=False,
    )
    adapter.process(source, output, settings, use_ai=True)
    with Image.open(output) as verified:
        assert verified.size == (256, 256)
        assert verified.mode == "RGBA"
        alpha = np.asarray(verified.getchannel("A"))
        assert alpha[0, 0] == 0
        assert alpha[80, 80] == 255
        assert alpha[128, 128] == 128
        assert 0 < alpha[40, 40] < 255
        # RGB under fractional alpha must retain the foreground ink colour.
        # A black/white matte baked into RGB causes visible fringes when a
        # transparent sticker is composited on a different background.
        rgba = np.asarray(verified.convert("RGBA"))
        foreground = np.array(ink_rgb, dtype=np.int16)
        for y, x in ((40, 40), (128, 128), (80, 80)):
            assert np.max(np.abs(rgba[y, x, :3].astype(np.int16) - foreground)) <= 1
        # Check the *entire* nonzero-alpha contour, not just three sample
        # pixels. A small local matte defect can be missed by point probes.
        # This fixture uses constant foreground RGB, so every covered pixel
        # must retain that ink regardless of fractional alpha coverage.
        covered = alpha > 0
        assert np.any((alpha > 0) & (alpha < 255))
        deviation = np.abs(rgba[:, :, :3].astype(np.int16) - foreground)
        assert np.max(deviation[covered]) <= 1
        # Verify black/white background composites agree with the straight
        # alpha equation. This is a deterministic fixture, NOT neural QA.
        a = alpha.astype(np.float32) / 255.0
        for background in (0.0, 255.0):
            actual = rgba[:, :, :3].astype(np.float32) * a[..., None] + background * (1.0 - a[..., None])
            expected = foreground.astype(np.float32) * a[..., None] + background * (1.0 - a[..., None])
            assert np.max(np.abs(actual[covered] - expected[covered])) <= 1.0
    assert log == [
        ("v2", 4, (32, 32)),
        ("hat", 4, (32, 32)),
        ("v2", 2, (128, 128)),
    ]


def test_8x_rgba_multicolour_opaque_plateaus_keep_distinct_inks(tmp_path):
    """Catch channel contamination across independent saturated ink regions.

    This is a deterministic routing regression, not a gradient, neural-model,
    multi-outline or real-world visual-quality certification.
    """
    log = []
    v2 = RecordingEngine("v2", log)
    hat = RecordingEngine("hat", log)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.create_job_engine = lambda settings: HATAssistEngine(v2, hat)
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(
                device_id="cpu", name="CPU",
            )
        ),
    )
    pixels = np.zeros((32, 32, 4), dtype=np.uint8)
    pixels[:, :16, :3] = (245, 35, 95)
    pixels[:, 16:, :3] = (20, 195, 240)
    pixels[4:28, 4:28, 3] = 255
    source = tmp_path / "two_inks.png"
    output = tmp_path / "two_inks_8x.png"
    Image.fromarray(pixels, "RGBA").save(source)
    settings = V21Settings(
        ai_scale=8, device="CPU", face_protection=False,
        resize_mode="stretch", v211_photo_model="v2_hat_assist",
        v21_precision_ink=False, graphic_ai=False,
    )
    adapter.process(source, output, settings, use_ai=True)
    with Image.open(output) as result:
        rgba = np.asarray(result.convert("RGBA"))
    assert rgba.shape == (256, 256, 4)
    for x, expected in ((64, (245, 35, 95)), (192, (20, 195, 240))):
        assert rgba[128, x, 3] == 255
        assert np.max(np.abs(
            rgba[128, x, :3].astype(np.int16)
            - np.array(expected, dtype=np.int16)
        )) <= 1
    assert rgba[0, 0, 3] == 0
    assert log == [
        ("v2", 4, (32, 32)),
        ("hat", 4, (32, 32)),
        ("v2", 2, (128, 128)),
    ]
