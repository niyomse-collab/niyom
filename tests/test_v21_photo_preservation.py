"""QA: V2.1 precision fill must not trade sharp lettering for plastic faces.

All images synthetic; no private customer files or printer ICC in GitHub.
"""
import cv2
import numpy as np
from PIL import Image

from signprint_ai.v21_precision_ink import (
    precision_ink_finish, photo_preservation_weight
)
from signprint_ai.v21_graphics_ai import V21Settings


def artwork():
    rng = np.random.default_rng(2026)
    rgb = np.full((320, 480, 3), [232, 220, 186], np.int16)
    rgb[50:290, 80:95] = [28, 45, 165]  # noisy 15px Thai-like narrow ink
    rgb[46:50, 84:90] = [28, 45, 165]   # separated tone-mark analogue
    rgb[40:290, 120:165] = [185, 40, 110]
    rgb[45:275, 235:425] = [184, 139, 111]  # smooth skin-like photo
    for y in range(45, 275):
        rgb[y, 235:425, :] += int(9*np.sin(y/38))
    noise = rng.integers(-4, 5, rgb.shape)
    noise[50:290, 80:95] = rng.integers(-14, 15, (240, 15, 3))
    noise[45:275, 235:425] = rng.integers(-6, 7, (230, 190, 3))
    return Image.fromarray(np.clip(rgb+noise, 0, 255).astype("uint8"))


def cfg(level):
    return V21Settings(
        denoise=0, flat_smoothing=level,
        text_graphic_boost=0, sharpness=0,
        contrast=0, saturation=0, v21_precision_ink=True
    )


def ink_grain(image):
    x = np.asarray(image)[80:250, 83:92, :].astype(float)
    return x.std(axis=(0, 1)).mean()


def test_0_to_100_ink_slider_changes_pixels_while_face_stays_original():
    source=artwork()
    levels=[0,25,50,75,100]
    outputs=[precision_ink_finish(source,cfg(l)) for l in levels]
    assert outputs[0].tobytes()==source.tobytes()
    grain=[ink_grain(i) for i in outputs]
    assert all(a>b for a,b in zip(grain,grain[1:])),grain
    assert grain[-1] < grain[0]*.25
    original=np.asarray(source)
    improved=np.asarray(outputs[-1])
    # Cream sign must not be erroneously classified as skin, while the face
    # is preserved exactly without requiring a Face Protect user selection.
    np.testing.assert_array_equal(improved[100:180,285:375],
                                  original[100:180,285:375])
    before=original[:,:,0]<100
    after=improved[:,:,0]<100
    np.testing.assert_array_equal(after,before)
    assert improved[47,86,2]>improved[47,86,0]


def test_photo_guard_stationary_across_disk_tile_padded_crops():
    source=artwork()
    result=np.asarray(precision_ink_finish(source,cfg(100)))
    original=np.asarray(source)
    # The 32px source window covers Gaussian sigma 6 and bilateral support.
    tile=Image.fromarray(original[40:280,85:395])
    padded=np.asarray(precision_ink_finish(tile,cfg(100)))
    np.testing.assert_allclose(
        result[80:230,125:355],
        padded[40:190,40:270], atol=1
    )


def test_photo_guard_keeps_alpha_and_explicit_face_regions():
    a=np.asarray(artwork())
    alpha=np.full(a.shape[:2],255,np.uint8)
    alpha[:,:35]=72
    source=Image.fromarray(np.dstack((a,alpha)),"RGBA")
    protected=((.16,.11,.22,.85),)
    result=np.asarray(precision_ink_finish(source,cfg(100),protected))
    np.testing.assert_array_equal(result[...,3],alpha)
    np.testing.assert_array_equal(result[:,:35,:],np.asarray(source)[:,:35,:])
    np.testing.assert_array_equal(result[40:280,77:109,:],
                                  np.asarray(source)[40:280,77:109,:])


def test_guide_only_limits_flat_smoothing_not_ink_sharpening():
    image=artwork()
    a=V21Settings(denoise=0,flat_smoothing=0,text_graphic_boost=0,
                  sharpness=0,contrast=0,saturation=0)
    b=V21Settings(denoise=0,flat_smoothing=0,text_graphic_boost=100,
                  sharpness=100,contrast=0,saturation=0)
    zero=precision_ink_finish(image,a)
    boosted=precision_ink_finish(image,b)
    assert zero.tobytes()==image.tobytes()
    assert boosted.tobytes()!=zero.tobytes()
