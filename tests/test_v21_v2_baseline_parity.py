"""Regression of accepted V2 output semantics inside V2.1, no V2 files touched.

The 2026-10-29 shop comparison reported worse ink flatness, object edges and
Thai lettering in V2.1 than approved V2. This test preserves a verifiable
reference algorithm while retaining optional experimental V2.1 filters.
"""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from signprint_ai import large_image
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v2_graphic_edges import refine_sign_edges
from signprint_ai.v21_v2_quality_baseline import refine_sign_edges as approved_v2_edges
from signprint_ai.v21_graphics_ai import V21Settings
from signprint_ai.v21_preview import render_finishing_preview


def original_test_image():
    pixels = np.full((128, 160, 3), (239, 229, 204), np.uint8)
    pixels[24:98, 36:53] = (25, 53, 166)
    pixels[28:107, 80:134] = (190, 41, 82)
    pixels[13:17, 37:42] = (25, 53, 166)
    pixels = cv2.GaussianBlur(pixels, (0, 0), 0.7)
    rng = np.random.default_rng(41)
    return Image.fromarray(
        np.clip(pixels.astype(int)+rng.integers(-9, 10, pixels.shape), 0, 255)
        .astype(np.uint8)
    )


def test_v21_default_is_previously_approved_v2_edge_algorithm():
    assert V21Settings().v21_v2_quality_baseline is True
    source = original_test_image()
    cfg = V21Settings(denoise=18, flat_smoothing=18, text_graphic_boost=28,
                      sharpness=26, contrast=8, saturation=0)
    expected = approved_v2_edges(source, settings=cfg)
    result = refine_sign_edges(source, settings=cfg)
    preview = render_finishing_preview(source, cfg)
    assert result.tobytes() == expected.tobytes() == preview.tobytes()


def test_v21_experimental_edges_are_separate_from_approved_v2():
    source = original_test_image()
    baseline = V21Settings(text_graphic_boost=80, flat_smoothing=75)
    experimental = V21Settings(text_graphic_boost=80, flat_smoothing=75,
                               v21_v2_quality_baseline=False)
    approved = np.asarray(refine_sign_edges(source, settings=baseline))
    trial = np.asarray(refine_sign_edges(source, settings=experimental))
    assert not np.array_equal(approved, trial)


def test_v2_quality_baseline_protects_alpha_and_selected_faces():
    rgb = np.asarray(original_test_image())
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    alpha[:, :16] = 128
    image = Image.fromarray(np.dstack((rgb, alpha)))
    region = ((.22, .12, .35, .78),)
    settings = V21Settings(face_protection=True, face_regions=region)
    approved = approved_v2_edges(image, protected_regions=region, settings=settings)
    v21 = render_finishing_preview(image, settings)
    assert approved.tobytes() == v21.tobytes()
    assert np.array_equal(np.asarray(v21)[..., 3], alpha)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("baseline,passes", [(True, [4, 2]), (False, [4])])
def test_print_scale_uses_v2_passes_only_in_baseline_mode(tmp_path, monkeypatch,
                                                           streaming, baseline, passes):
    from signprint_ai import independent_core
    calls = []

    class Engine:
        upsampler = SimpleNamespace(tile_size=512, tile_pad=10)
        def enhance_tile(self, rgb, scale, cancel):
            calls.append(scale)
            return np.repeat(np.repeat(rgb, scale, axis=0), scale, axis=1)
        def enhance(self, src, dst, scale, **kw):
            with Image.open(src) as im:
                Image.fromarray(self.enhance_tile(np.asarray(im.convert("RGB")), scale,
                                                   None)).save(dst)
        def device_name(self):
            return "CPU"

    monkeypatch.setattr(independent_core, "DeviceManager",
                        lambda: SimpleNamespace())
    adapter = NiyomSilpCoreAdapter()
    adapter.engine_manager.create_engine = lambda device: Engine()
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1 if streaming else 10**9)
    src, dst = tmp_path/"input.png", tmp_path/"result.png"
    Image.new("RGB", (68, 100), (30, 50, 120)).save(src)
    settings = V21Settings(v21_v2_quality_baseline=baseline,
                           ai_scale=4, denoise=0, flat_smoothing=0,
                           text_graphic_boost=0, sharpness=0, contrast=0,
                           saturation=0, print_width=3.54, print_height=5.21,
                           print_unit="inch", dpi=100)
    result = adapter.process(src, dst, settings)
    assert calls == passes
    assert result["ai_scale"] == (8 if baseline else 4)
    assert Image.open(dst).size == (354, 521)
