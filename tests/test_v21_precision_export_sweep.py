"""V2.1 finishing sweep THROUGH the actual adapter export paths.

The AI engine is a deterministic synthetic stand-in so CPU-only CI can exercise
both real PNG export and tiled libvips I/O. Installed EXE separately runs real
Real-ESRGAN inference plus its own bundled precision-slider smoke test.
"""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from signprint_ai import independent_core, large_image
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v21_graphics_ai import V21Settings


def source_ink():
    arr = np.full((144, 144, 3), (236, 226, 198), np.int16)
    arr[25:118, 62:73] = (30, 45, 130)
    arr[30:112, 85:111] = (180, 45, 95)
    arr[12:18, 62:73] = (30, 45, 130)
    arr += np.random.default_rng(73).integers(-10, 11, arr.shape)
    return np.clip(arr, 0, 255).astype(np.uint8)


def settings(level, *, advanced):
    return V21Settings(
        ai_scale=2, device="cpu", flat_smoothing=level,
        v21_v2_quality_baseline=True, v21_precision_ink=advanced,
        denoise=0, text_graphic_boost=0, contrast=0,
        sharpness=0, saturation=0,
    )


def stroke_grain(pixels):
    # 11px stroke doubled to 22px; crop well within its ink fill.
    ink = pixels[60:210, 128:140, :3].astype(np.float32)
    return float(ink.std(axis=(0, 1)).mean())


@pytest.mark.parametrize("disk_tiles", [False, True])
def test_ink_slider_levels_reach_real_png_export(tmp_path, monkeypatch, disk_tiles):
    class FakeEngine:
        upsampler = SimpleNamespace(tile_size=48, tile_pad=18)
        def enhance_tile(self, pixels, scale, cancel):
            return np.repeat(np.repeat(pixels, scale, 0), scale, 1)
        def enhance(self, source, dest, scale, **kwargs):
            with Image.open(source) as img:
                Image.fromarray(
                    self.enhance_tile(np.asarray(img.convert("RGB")), scale, None)
                ).save(dest)
        def device_name(self):
            return "CPU"

    monkeypatch.setattr(independent_core, "DeviceManager", lambda: SimpleNamespace())
    adapter = NiyomSilpCoreAdapter()
    adapter.engine_manager.create_engine = lambda _device: FakeEngine()
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS",
                        1 if disk_tiles else 10**9)
    inp = tmp_path / "original.png"
    Image.fromarray(source_ink()).save(inp)
    output = []
    for level in (0, 25, 50, 75, 100):
        dest = tmp_path / f"level_{level}.png"
        result = adapter.process(inp, dest, settings(level, advanced=True))
        assert result["processing_mode"] == ("disk_tiles" if disk_tiles else "memory")
        with Image.open(dest) as img:
            assert img.size == (288, 288)
            output.append(np.asarray(img).copy())
    grades = [stroke_grain(x) for x in output]
    assert all(a > b for a, b in zip(grades, grades[1:])), grades
    assert grades[-1] < grades[0] * .70, grades
    # A distant detached tone mark must remain visibly detached at maximum.
    assert output[-1][30, 135, 2] > output[-1][30, 135, 0]
    assert output[-1][42, 135, 0] > output[-1][42, 135, 2]


@pytest.mark.parametrize("disk_tiles", [False, True])
def test_extra_stage_beats_frozen_v2_only_in_solid_ink_roi(tmp_path, monkeypatch,
                                                            disk_tiles):
    class FakeEngine:
        upsampler = SimpleNamespace(tile_size=48, tile_pad=18)
        def enhance_tile(self, pixels, scale, cancel):
            return np.repeat(np.repeat(pixels, scale, 0), scale, 1)
        def enhance(self, source, dest, scale, **kwargs):
            with Image.open(source) as img:
                Image.fromarray(
                    self.enhance_tile(np.asarray(img.convert("RGB")), scale, None)
                ).save(dest)
        def device_name(self):
            return "CPU"

    monkeypatch.setattr(independent_core, "DeviceManager", lambda: SimpleNamespace())
    adapter = NiyomSilpCoreAdapter()
    adapter.engine_manager.create_engine = lambda _device: FakeEngine()
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS",
                        1 if disk_tiles else 10**9)
    inp = tmp_path / "original.png"
    Image.fromarray(source_ink()).save(inp)
    data = {}
    for advanced in (False, True):
        dest = tmp_path / f"advanced_{advanced}.png"
        adapter.process(inp, dest, settings(100, advanced=advanced))
        with Image.open(dest) as img:
            data[advanced] = np.asarray(img).copy()
    assert stroke_grain(data[True]) < stroke_grain(data[False]) * .8
    # V2.1's gain must not erase the letter or invert its ink colour.
    assert data[True][80, 132, 2] > data[True][80, 132, 0]
