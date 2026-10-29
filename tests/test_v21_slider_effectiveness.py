"""V2.1 proof that finishing sliders affect *preview and actual pixels*.

Synthetic ink strokes only; no private customer artwork in repository.
"""
import cv2
import numpy as np
from PIL import Image

from signprint_ai.v21_graphics_ai import V21Settings
from signprint_ai.v21_preview import render_finishing_preview
from signprint_ai.v2_graphic_edges import refine_sign_edges


def _controls(**kwargs):
    options = dict(denoise=0, flat_smoothing=0, text_graphic_boost=0,
                   sharpness=0, contrast=0, saturation=0)
    options.update(kwargs)
    return V21Settings(**options)


def _thin_ink():
    rgb = np.full((144, 144, 3), (236, 226, 198), np.uint8)
    rgb[25:118, 62:73] = (30, 45, 130)  # 11-pixel narrow letter stroke
    rgb[30:112, 85:111] = (180, 45, 95)  # broader contrasting ink
    rgb[12:18, 62:73] = (30, 45, 130)  # detached Thai-mark analogue
    noise = np.random.default_rng(73).integers(-10, 11, rgb.shape)
    return Image.fromarray(np.clip(rgb.astype(int) + noise, 0, 255).astype("uint8"))


def _grain(rgb):
    # Safe interior of the narrow solid-colour stroke, away from its edge.
    return np.asarray(rgb)[30:110, 65:70, :].astype(float).std(axis=(0, 1)).mean()


def test_preview_zero_is_identity_and_responds_to_flat_slider():
    source = _thin_ink()
    zero = render_finishing_preview(source, _controls())
    mid = render_finishing_preview(source, _controls(flat_smoothing=25))
    full = render_finishing_preview(source, _controls(flat_smoothing=100))
    assert zero.tobytes() == source.tobytes()
    assert _grain(full) < _grain(mid) < _grain(zero)
    assert _grain(full) < _grain(zero) * 0.6
    # Avoid changing stroke geometry or deleting the tiny detached mark.
    original_mask = np.asarray(source)[..., 0] < 110
    np.testing.assert_array_equal(np.asarray(full)[..., 0] < 110, original_mask)


def test_preview_uses_exact_export_finishing_filter():
    source = _thin_ink()
    active = _controls(denoise=70, flat_smoothing=80, text_graphic_boost=30,
                       sharpness=25, contrast=10)
    preview = render_finishing_preview(source, active)
    export_finish = refine_sign_edges(source, settings=active)
    assert preview.tobytes() == export_finish.tobytes()


def test_legacy_setting_does_not_enable_v21_fill_algorithm():
    from signprint_ai.processing import EnhanceSettings
    assert not hasattr(EnhanceSettings(), "v21_color_cleanup")
    source = _thin_ink()
    v21 = np.asarray(refine_sign_edges(source, settings=_controls(flat_smoothing=100)))
    legacy = np.asarray(refine_sign_edges(source, settings=EnhanceSettings(
        denoise=0, flat_smoothing=100, text_graphic_boost=0,
        contrast=0, sharpness=0, saturation=0)))
    assert _grain(v21) < _grain(legacy)


def test_alpha_plane_and_protected_face_are_unchanged():
    source = np.asarray(_thin_ink())
    alpha = np.full(source.shape[:2], 255, np.uint8)
    alpha[:, :12] = 96
    rgba = Image.fromarray(np.dstack((source, alpha)))
    settings = _controls(flat_smoothing=100, face_protection=True,
                         face_regions=((.42, .2, .54, .8),))
    result = np.asarray(render_finishing_preview(rgba, settings))
    np.testing.assert_array_equal(result[..., 3], alpha)
    np.testing.assert_array_equal(result[28:115, 60:78], np.asarray(rgba)[28:115, 60:78])
