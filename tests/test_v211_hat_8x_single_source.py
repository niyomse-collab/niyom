"""8x HAT Assist may enhance only the original source, not an intermediate.

These are pipeline-routing regressions with deterministic fake engines. They
do NOT certify image quality or exercise real checkpoint inference.
"""
from types import SimpleNamespace

import numpy as np
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
