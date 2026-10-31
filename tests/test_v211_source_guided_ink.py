"""Protect sign ink quality, RGBA and people in the source-guided experiment.

Only native-HR benchmark using pinned official V2 weights can demonstrate
whether the real SR network's artificial intrastroke pigmentation was fixed.
These tests are non-neural safety regressions, not shop acceptance.
"""
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from signprint_ai.v211_source_guided_ink import (
    source_guided_red_ink, restore_source_guided_ink,
)


def _sample():
    image = Image.new("RGB", (192, 192), (62, 58, 86))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=29)
    draw.text((10, 90), "SALE 30", fill=(243, 27, 29), font=font)
    truth = np.asarray(image).copy()
    src = np.asarray(
        image.resize((96, 96), Image.Resampling.LANCZOS)
    ).copy()
    src = cv2.GaussianBlur(src, (0, 0), .6)
    return truth, src


def _model_artifact():
    truth, src = _sample()
    out = truth.copy().astype(np.float32)
    # Artificial dark pigment appears INSIDE a narrow red stroke after an
    # SR model, while the original LR source still carries correct hue ratios.
    red = (out[...,0]-out[...,1] > 70) & (out[...,0] > 120)
    yy, xx = np.indices(red.shape)
    ripple = 35 + 23*np.sin(xx*.45+yy*.22)
    out[red,0] = np.maximum(90, out[red,0]-ripple[red])
    out[red,1] = out[red,1]+7
    out[red,2] = np.maximum(0, out[red,2]-14)
    return truth, src, np.rint(np.clip(out,0,255)).astype(np.uint8)


def _psnr(truth, image):
    return 10*np.log10(255**2/np.mean(
        (truth.astype(np.float64)-image.astype(np.float64))**2
    ))


def test_realistic_source_guidance_helps_dark_colour_inside_red_letters():
    truth, src, sr=_model_artifact()
    result,audit=source_guided_red_ink(sr,src)
    assert audit["quality_certified"] is False
    assert audit["eligible"]
    assert _psnr(truth,result)>_psnr(truth,sr)+.25
    assert audit["changed_pixels_pct"]>0


def test_already_clean_red_block_is_bitwise_unchanged():
    image=np.full((192,192,3),(62,58,86),np.uint8)
    image[25:170,20:175]=(245,24,30)
    small=np.asarray(Image.fromarray(image).resize((96,96),Image.Resampling.LANCZOS))
    result,audit=source_guided_red_ink(image,small)
    np.testing.assert_array_equal(result,image)
    assert audit["reason"] in ("already_uniform_flat_ink",
                               "source_red_stroke_not_confident")


def test_photograph_noise_cannot_trigger_source_ink_red_restoration():
    rng=np.random.default_rng(808)
    photo=rng.integers(0,255,(192,192,3),dtype=np.uint8)
    source=np.asarray(Image.fromarray(photo).resize((96,96),Image.Resampling.LANCZOS))
    out,audit=source_guided_red_ink(photo,source)
    np.testing.assert_array_equal(out,photo)
    assert audit["reason"]=="photographic_texture_keep_v2"


def test_png_alpha_and_hidden_matte_remain_byte_exact():
    truth,src,sr=_model_artifact()
    rgba=np.dstack((sr,np.full((192,192),255,np.uint8)))
    rgba[:20,:,3]=0
    rgba[-20:,:,3]=0
    image=Image.fromarray(rgba,"RGBA")
    result,audit=restore_source_guided_ink(image,Image.fromarray(src))
    assert result.mode=="RGBA"
    np.testing.assert_array_equal(
        np.asarray(result.getchannel("A")),rgba[:,:,3]
    )
    np.testing.assert_array_equal(
        np.asarray(result.convert("RGB"))[:16],rgba[:16,:,:3]
    )


def test_selected_face_crop_is_pixel_exact():
    truth,src,sr=_model_artifact()
    out,audit=source_guided_red_ink(
        sr,src,protected_regions=((.03,.42,.92,.80),)
    )
    np.testing.assert_array_equal(out[85:142,20:166],sr[85:142,20:166])


@pytest.mark.parametrize("strength",[-1,1.2,float("nan"),float("inf")])
def test_invalid_strength_is_rejected(strength):
    _,src,sr=_model_artifact()
    with pytest.raises(ValueError):
        source_guided_red_ink(sr,src,strength=strength)


def test_zero_strength_keeps_original_without_spurious_colors():
    _,src,sr=_model_artifact()
    out,audit=source_guided_red_ink(sr,src,strength=0)
    np.testing.assert_array_equal(out,sr)
    assert not audit["quality_certified"]


def test_non_red_print_strokes_are_not_changed():
    image=Image.new("RGB",(192,192),(62,58,86))
    d=ImageDraw.Draw(image)
    d.line((20,20,150,150),fill=(12,22,28),width=9)
    d.line((20,60,150,60),fill=(252,214,17),width=7)
    rgb=np.asarray(image).copy()
    src=np.asarray(image.resize((96,96),Image.Resampling.LANCZOS))
    out,audit=source_guided_red_ink(rgb,src)
    np.testing.assert_array_equal(out,rgb)
    assert not audit["eligible"]
