"""V2.1+ acceptance: the additional stage must beat plain V2 on synthetic ink.

Synthetic regressions are NOT equivalent to verifying shop images or printing.
"""
import numpy as np
import cv2
from PIL import Image

from signprint_ai.v21_precision_ink import precision_ink_finish
from signprint_ai.v21_graphics_ai import V21Settings
from signprint_ai.v2_graphic_edges import refine_sign_edges
from signprint_ai.v21_v2_quality_baseline import refine_sign_edges as accepted_v2


def artwork():
    rng = np.random.default_rng(33)
    px = np.full((220, 320, 3), [235, 218, 196], dtype=np.int16)
    px[25:190, 80:93] = [22, 40, 151]  # thin Thai-stroke analogue
    px[20:25, 84:88] = [22, 40, 151]   # detached tone mark
    px[33:175, 130:220] = [194, 38, 70]
    cv2.circle(px, (270, 105), 30, (28, 145, 193), -1)
    noisy = np.clip(px + rng.integers(-18, 19, px.shape), 0, 255)
    return Image.fromarray(noisy.astype("uint8"))


def settings(level, **kwargs):
    return V21Settings(denoise=0, flat_smoothing=level, text_graphic_boost=0,
                       sharpness=0, contrast=0, saturation=0,
                       v21_v2_quality_baseline=True,
                       v21_precision_ink=True, **kwargs)


def grain(image):
    x = np.asarray(image)[40:170, 83:90].astype(np.float32)
    return x.std(axis=(0, 1)).mean()


def test_flat_slider_0_25_50_75_100_reduces_letter_ink_speckle():
    src = artwork()
    outcomes = [precision_ink_finish(src, settings(v)) for v in (0,25,50,75,100)]
    measured = [grain(result) for result in outcomes]
    assert outcomes[0].tobytes() == src.tobytes()
    assert all(a > b for a,b in zip(measured, measured[1:])), measured
    assert measured[-1] < measured[0]*.25
    # Stroke shape and detached mark survive even at 100.
    start = np.asarray(src)[:, :, 0] < 95
    end = np.asarray(outcomes[-1])[:, :, 0] < 95
    np.testing.assert_array_equal(start, end)


def test_v21_advanced_is_better_than_frozen_v2_grain_on_same_input():
    src = artwork()
    v2 = V21Settings(denoise=0, flat_smoothing=100, text_graphic_boost=0,
                     sharpness=0, contrast=0, saturation=0,
                     v21_v2_quality_baseline=True,
                     v21_precision_ink=False)
    v21 = V21Settings(denoise=0, flat_smoothing=100, text_graphic_boost=0,
                      sharpness=0, contrast=0, saturation=0,
                      v21_v2_quality_baseline=True,
                      v21_precision_ink=True)
    old = accepted_v2(src, settings=v2)
    new = refine_sign_edges(src, settings=v21)
    assert grain(new) < grain(old)*.75
    assert old.tobytes() == refine_sign_edges(src, settings=v2).tobytes()


def test_rgb_chromatic_edge_and_detached_mark_remain_distinct():
    src = artwork()
    new = precision_ink_finish(src, settings(100))
    arr = np.asarray(new)
    assert arr[22, 85, 2] > arr[22, 85, 0]
    assert arr[12, 85, 0] > arr[12, 85, 2]
    assert np.all(arr[95, 86] != arr[95, 150])


def test_transparency_and_face_roi_are_pixel_identical():
    source = np.asarray(artwork())
    alpha = np.full(source.shape[:2], 255, np.uint8)
    alpha[:, :40] = 88
    rgba = Image.fromarray(np.dstack((source, alpha)), "RGBA")
    protected = ((.20,.12,.35,.85),)
    result = precision_ink_finish(rgba, settings(100), protected)
    image = np.asarray(result)
    np.testing.assert_array_equal(image[:,:,3], alpha)
    np.testing.assert_array_equal(image[:,:40,:], np.asarray(rgba)[:,:40,:])
    np.testing.assert_array_equal(image[30:180,60:117,:],
                                  np.asarray(rgba)[30:180,60:117,:])


def test_text_and_sharpen_sliders_act_on_high_chroma_boundaries():
    src = artwork()
    zero = precision_ink_finish(src, settings(0))
    active = V21Settings(denoise=0,flat_smoothing=0,
                         text_graphic_boost=100,sharpness=100,
                         contrast=0,saturation=0)
    new = precision_ink_finish(src, active)
    assert zero.tobytes() == src.tobytes()
    old_px, new_px = np.asarray(src), np.asarray(new)
    assert np.count_nonzero(old_px != new_px) > 0
    assert np.abs(old_px.astype(int)-new_px.astype(int)).max() <= 10


def test_v2_legacy_unaffected_when_advanced_off():
    src=artwork()
    mode=V21Settings(v21_v2_quality_baseline=True,
                     v21_precision_ink=False)
    original = accepted_v2(src, settings=mode)
    output = refine_sign_edges(src, settings=mode)
    assert original.tobytes() == output.tobytes()
