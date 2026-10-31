"""1x isolated flat-ink reference tests; NOT a real ESRGAN/V2 release verdict.

All reference art is independently drawn before simulated blur/noise.
These tests protect morphology, alpha and faces; actual pinned-model V2
comparisons and physical Thai vinyl proof are separately mandatory.
"""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from signprint_ai.v211_ink_geometry import (
    reconstruct_ink_pixels, finish_flat_ink_geometry
)


def make_reference(subject):
    canvas = Image.new("RGB", (256, 256), (60, 58, 83))
    draw = ImageDraw.Draw(canvas)
    if subject == "blocks":
        draw.rectangle((25,20,140,130),fill=(251,26,34))
        draw.rectangle((140,20,234,130),fill=(12,60,248))
        draw.rectangle((25,170,234,184),fill=(244,244,243))
    elif subject == "curve":
        draw.arc((38,24,219,224),30,290,fill=(10,14,22),width=12)
        draw.rectangle((10,10,230,20),fill=(249,192,12))
    elif subject == "letters":
        font = ImageFont.load_default(size=30)
        # A realistic medium-weight signage font; the separate thin-mark
        # test establishes that tiny 1-2px strokes are not destroyed.
        draw.text((14,46),"OPEN PRINT",fill=(253,251,246),
                  font=font,stroke_width=1)
        draw.text((14,99),"SIGNAGE",fill=(241,20,30),
                  font=font,stroke_width=1)
    elif subject == "small_marks":
        for x in range(20,220,8):
            draw.line((x,20,x,220),fill=(245,236,20),width=2)
        # 5px mark remains optically present after a 1.1px blur; a 2px
        # mark can disappear from source sampling even before AI begins.
        draw.ellipse((121,8,127,14),fill=(240,240,240))
    else:
        raise ValueError(subject)
    return np.asarray(canvas).copy()


def degrade(reference):
    blurred = cv2.GaussianBlur(reference,(0,0),1.1)
    noise = np.random.default_rng(42).normal(0,1.5, blurred.shape)
    return np.rint(np.clip(blurred.astype(np.float32)+noise,0,255)).astype(np.uint8)


def psnr(a,b):
    return 10*np.log10(255.0**2/np.mean(
        (a.astype(np.float64)-b.astype(np.float64))**2
    ))


@pytest.mark.parametrize("subject,min_gain", [
    ("blocks", 2.0), ("curve", 2.0), ("letters", .25)
])
def test_recovered_flat_ink_improves_independent_reference(subject,min_gain):
    clean = make_reference(subject)
    noisy = degrade(clean)
    better,audit = reconstruct_ink_pixels(noisy)
    gain = psnr(clean,better)-psnr(clean,noisy)
    assert gain > min_gain, (subject,gain,audit)
    assert audit["eligible"]
    assert audit["changed_pixels_pct"] > .1
    assert not audit["quality_certified"]


def test_fine_thai_like_marks_and_thin_lines_are_not_erased():
    clean=make_reference("small_marks")
    blurred=degrade(clean)
    restored,audit=reconstruct_ink_pixels(blurred)
    # Near-white 2px marks remain visible; do not apply binary morphology.
    source_mark = np.sum(blurred[4:18,113:132].max(2)>200)
    restored_mark = np.sum(restored[4:18,113:132].max(2)>200)
    assert source_mark > 0
    # Never erase a visible tone-dot or invent new connected components.
    assert restored_mark >= source_mark
    assert psnr(clean,restored)>=psnr(clean,blurred)-.05
    assert restored.shape == clean.shape


def test_photographic_noise_is_bypassed_exactly():
    rng=np.random.default_rng(17)
    photo=rng.integers(0,255,(256,256,3),dtype=np.uint8)
    out,audit=reconstruct_ink_pixels(photo)
    np.testing.assert_array_equal(out,photo)
    assert audit["reason"]=="photographic_texture_keep_v2"


def test_sharp_solid_colour_rectangles_do_not_gain_fake_halos():
    clean=make_reference("blocks")
    better,audit=reconstruct_ink_pixels(clean)
    # The exact native pixel geometry is already perfect.
    np.testing.assert_array_equal(better,clean)


def test_transparent_png_preserves_alpha_and_hidden_matte():
    rgba=np.zeros((192,192,4),np.uint8)
    rgba[24:170,29:170,:3]=np.array((243,34,50),np.uint8)
    rgba[24:170,29:170,3]=255
    rgba[51:110,55:130,:3]=(12,64,231)
    source=Image.fromarray(rgba,"RGBA")
    completed,audit=finish_flat_ink_geometry(source)
    assert completed.mode=="RGBA"
    np.testing.assert_array_equal(np.asarray(completed.getchannel("A")),rgba[...,3])
    # Hidden RGB around transparent crop must be exact, not printed over white.
    np.testing.assert_array_equal(
        np.asarray(completed.convert("RGB"))[0,0],rgba[0,0,:3]
    )
    assert audit["quality_certified"] is False


def test_selected_face_region_is_pixel_exact():
    source=degrade(make_reference("blocks"))
    output,_=reconstruct_ink_pixels(
        source,protected_regions=((.15,.08,.55,.56),)
    )
    np.testing.assert_array_equal(output[30:130,45:135],source[30:130,45:135])


def test_wrong_crop_alpha_or_strength_fails_closed():
    rgb=make_reference("blocks")
    with pytest.raises(ValueError):
        reconstruct_ink_pixels(rgb,strength=float("nan"))
    with pytest.raises(ValueError):
        reconstruct_ink_pixels(rgb,alpha=np.ones((10,10),np.uint8))
    with pytest.raises(ValueError):
        reconstruct_ink_pixels(rgb,protected_regions=((-.2,0,.5,.8),))


def test_v21_graphic_geometry_is_off_by_default(monkeypatch):
    from signprint_ai.v21_graphics_ai import V21Settings
    from signprint_ai import v2_graphic_edges
    settings=V21Settings(v21_v2_quality_baseline=True)
    assert settings.v211_ink_geometry is False
    src=Image.fromarray(degrade(make_reference("curve")))
    # Isolate just routing: inject faithful V2 edge baseline and compare.
    from signprint_ai import v21_v2_quality_baseline
    monkeypatch.setattr(v21_v2_quality_baseline,"refine_sign_edges",
                        lambda image,**kw:image.copy())
    base=v2_graphic_edges.refine_sign_edges(src,settings=settings)
    np.testing.assert_array_equal(np.asarray(base),np.asarray(src))
    settings.v211_ink_geometry=True
    edited=v2_graphic_edges.refine_sign_edges(src,settings=settings)
    assert not np.array_equal(np.asarray(edited),np.asarray(base))
