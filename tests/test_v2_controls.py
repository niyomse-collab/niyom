"""Behavioral regression: UI controls reach both V2 processing routes."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from signprint_ai import large_image, niyomsil_core_adapter as core
from signprint_ai.processing import EnhanceSettings
from signprint_ai.v2_graphic_edges import refine_sign_edges

CONTROLS = ('denoise', 'flat_smoothing', 'text_graphic_boost', 'sharpness')


def fixture_pixels():
    rgb = np.full((96, 96, 3), (232, 218, 174), dtype=np.uint8)
    rgb[28:76, 20:78] = (28, 47, 126)
    rgb[14:19, 38:44] = (28, 47, 126)
    rgb = cv2.GaussianBlur(rgb, (0, 0), .8)
    noise = np.random.default_rng(73).integers(-5, 6, rgb.shape)
    return np.clip(rgb.astype(int) + noise, 0, 255).astype(np.uint8)


def settings(**kwargs):
    return EnhanceSettings(**(dict.fromkeys(CONTROLS, 0) | kwargs))


def test_all_zero_is_exact_bypass_and_preserves_alpha():
    rgb = fixture_pixels()
    alpha = np.arange(96 * 96, dtype=np.uint8).reshape(96, 96)
    image = Image.fromarray(np.dstack((rgb, alpha)))
    assert refine_sign_edges(image, settings=settings()).tobytes() == image.tobytes()


@pytest.mark.parametrize('control', CONTROLS)
def test_individual_control_changes_pixels_with_bounded_effect(control):
    rgb = fixture_pixels()
    result = np.asarray(refine_sign_edges(Image.fromarray(rgb), settings=settings(**{control: 100})))
    diff = np.abs(result.astype(int) - rgb.astype(int))
    assert diff.max() > 0
    assert diff.max() <= 15
    # Detached mark and its surrounding background stay distinct.
    assert result[16, 40, 2] > result[16, 40, 0]
    assert result[10, 40, 0] > result[10, 40, 2]


def test_controls_preserve_selected_face_and_translucent_border():
    rgb = fixture_pixels()
    alpha = np.full((96, 96), 255, dtype=np.uint8)
    alpha[:, :10] = 80
    image = Image.fromarray(np.dstack((rgb, alpha)))
    out = np.asarray(refine_sign_edges(image, settings=settings(**dict.fromkeys(CONTROLS, 100)),
                                      protected_regions=((.4, .2, .8, .8),)))
    np.testing.assert_array_equal(out[..., 3], alpha)
    np.testing.assert_array_equal(out[:, :14, :3], rgb[:, :14])
    np.testing.assert_array_equal(out[20:76, 39:76, :3], rgb[20:76, 39:76])


@pytest.mark.parametrize('streaming', [False, True])
@pytest.mark.parametrize('control', CONTROLS)
def test_slider_affects_export_even_when_face_recovery_fails(tmp_path, monkeypatch, streaming, control):
    class Engine:
        upsampler = SimpleNamespace(tile_size=48, tile_pad=10)
        def enhance_tile(self, pixels, scale, cancel):
            return np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        def enhance(self, src, dst, scale, **kwargs):
            with Image.open(src) as image:
                Image.fromarray(self.enhance_tile(np.asarray(image.convert('RGB')), scale, None)).save(dst)
        def device_name(self):
            return 'CPU'

    adapter = core.NiyomSilpCoreAdapter.__new__(core.NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        create_engine=lambda device: Engine(),
        device_manager=SimpleNamespace(get_default_device=lambda: SimpleNamespace(device_id='cpu')))
    def fail(*args, **kwargs):
        raise RuntimeError('simulated face backend failure')
    adapter.face_module = SimpleNamespace(apply=fail)
    # Large face helper normally catches backend errors itself.
    from signprint_ai import large_faces
    monkeypatch.setattr(large_faces, 'apply_faces', lambda adapter, image, *args: (
        image, {'enabled': True, 'applied': False, 'skipped_reason': 'simulated failure'}))
    monkeypatch.setattr(large_image, 'IN_MEMORY_PIXELS', 1 if streaming else 10**9)
    src = tmp_path / 'source.png'
    Image.fromarray(fixture_pixels()).save(src)
    zero, active = tmp_path / 'zero.png', tmp_path / 'active.png'
    adapter.process(src, zero, settings(face_protection=True))
    adapter.process(src, active, settings(face_protection=True, **{control: 100}))
    with Image.open(zero) as a, Image.open(active) as b:
        assert a.size == b.size == (384, 384)
        assert a.tobytes() != b.tobytes()
