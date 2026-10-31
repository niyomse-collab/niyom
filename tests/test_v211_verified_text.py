"""V2.1.1 opt-in verified text proof: correct Unicode and real final-size glyphs.

No font bundled. The runtime resolves an installed font and requires HarfBuzz
RAQM to shape Thai; if a system cannot render Thai safely, it must fail closed
rather than giving the operator a malformed tone mark.
"""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont, features

from signprint_ai.v211_verified_text import (
    VerifiedTextRegion, exact_text_overlay,
    replace_on_verified_flat_background, apply_verified_regions,
)


def local_font():
    for name in (
        "DejaVuSans.ttf",
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        try:
            font = ImageFont.truetype(name, 16)
            if Path(font.path).is_file():
                return font.path
        except (OSError, AttributeError):
            continue
    pytest.skip("No available installed test font")


def thai_font():
    for name in (
        "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
        "/usr/share/fonts/truetype/thai-tlwg/Garuda.ttf",
        "/usr/share/fonts/opentype/tlwg/Garuda.otf",
        "C:/Windows/Fonts/leelawui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ):
        try:
            if Path(name).is_file():
                return name
        except OSError:
            pass
    pytest.skip("Thai font not installed on this CI worker")


def region(*, font=None, mode="replace_flat", text="SALE 30"):
    return VerifiedTextRegion(32, 35, 210, 65, text, font or local_font(),
                              49, (246, 25, 35), "center", mode)


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_text_only_overlay_has_no_opaque_background():
    overlay, audit = exact_text_overlay(
        (280, 160), region(mode="transparent_overlay")
    )
    a = np.asarray(overlay)
    assert overlay.mode == "RGBA"
    assert a.shape == (160, 280, 4)
    assert np.count_nonzero(a[..., 3]) > 200
    assert np.all(a[:30, :, 3] == 0)
    assert np.all(a[110:, :, 3] == 0)
    assert np.all(a[..., 3][a[..., 3] == 0] == 0)
    assert audit["exact_text"] == "SALE 30"
    assert audit["no_background_generated"] is True


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_overwrite_only_inside_selected_flat_region_removes_mottled_old_ink():
    source = Image.new("RGB", (280, 160), (52, 51, 79))
    drawing = ImageDraw.Draw(source)
    drawing.text((50, 45), "SALE 30", font=ImageFont.truetype(local_font(), 36),
                 fill=(172, 37, 94))
    original = np.asarray(source).copy()
    out, audit = replace_on_verified_flat_background(source, region())
    pixels = np.asarray(out.convert("RGB"))
    # 100% pixel identity outside confirmed ROI: not a global colour filter.
    outside = np.ones((160, 280), dtype=bool)
    outside[35:100, 32:242] = False
    np.testing.assert_array_equal(pixels[outside], original[outside])
    assert pixels[60:80, 70:170, 0].max() >= 230
    assert audit["verified_user_text"]
    assert audit["unchanged_outside_selected_rectangle"]


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_transparent_cutout_never_gains_white_flat_background():
    rgba = np.zeros((160, 280, 4), dtype=np.uint8)
    rgba[40:120, 40:240] = (230, 40, 35, 255)
    original = Image.fromarray(rgba, "RGBA")
    with pytest.raises(ValueError, match="Transparent cutout"):
        replace_on_verified_flat_background(original, region())
    restored, audits = apply_verified_regions(
        original, (region(mode="transparent_overlay"),)
    )
    assert restored.mode == "RGBA"
    al = np.asarray(restored.getchannel("A"))
    assert np.all(al[:30] == 0) and np.all(al[-30:] == 0)
    assert al[60:85, 70:180].max() == 255
    assert audits[0]["no_background_generated"]


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_nonuniform_or_photo_background_fails_closed():
    rgba = np.zeros((160, 280, 3), dtype=np.uint8)
    rgba[:, :, 0] = np.linspace(10, 220, 280).astype("uint8")
    rgba[:, :, 1] = 75
    rgba[:, :, 2] = 160
    with pytest.raises(ValueError, match="Nonuniform"):
        replace_on_verified_flat_background(Image.fromarray(rgba), region())


def test_missing_font_and_outside_canvas_never_render():
    r = region(font="/not/a/real/font.ttf")
    with pytest.raises(FileNotFoundError):
        exact_text_overlay((280, 160), r)
    r2 = VerifiedTextRegion(260, 10, 100, 80, "SALE", local_font(), 32)
    with pytest.raises(ValueError, match="exceed"):
        exact_text_overlay((280, 160), r2)


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_thai_vowels_and_tone_marks_render_without_cropped_bounding_box():
    font = thai_font()
    text = "ซื้อ ชื่อ ป้ายไวนิล โปรโมชั่น"
    rect = VerifiedTextRegion(20, 20, 650, 155, text, font, 72,
                              (245, 20, 30), "center", "transparent_overlay")
    overlay, audit = exact_text_overlay((700, 210), rect)
    alpha = np.asarray(overlay.getchannel("A"))
    assert np.count_nonzero(alpha) > 200
    assert audit["exact_text"] == text  # Exact, no OCR normalization
    assert alpha[25:170, 25:670].max() == 255
    assert np.all(alpha[:20] == 0)
    assert np.all(alpha[175:] == 0)


class FakeV2:
    def enhance(self, src, dst, *, scale=2, progress_callback=None, cancel_check=None):
        with Image.open(src) as image:
            out = image.convert("RGB").resize(
                (image.width*scale, image.height*scale),
                Image.Resampling.BICUBIC
            )
            out.save(dst)
        return {"model": "accepted V2 test stub"}


def adapter_with_stub():
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.create_job_engine = lambda settings: FakeV2()
    adapter.engine_manager = SimpleNamespace(
        engine=None, device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(
                device_id="cpu", name="CPU"
            )
        )
    )
    return adapter


@pytest.mark.skipif(not features.check("raqm"), reason="RAQM unavailable")
def test_real_v211_output_includes_verified_text_only_after_neural_resize(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    src, dst = tmp_path/"source.png", tmp_path/"shop.png"
    Image.new("RGB", (140, 80), (52, 51, 79)).save(src)
    settings = V21Settings(
        ai_scale=2, dpi=300, face_protection=False,
        v211_verified_text_regions=(region(),),
    )
    result = adapter_with_stub().process(src, dst, settings, use_ai=True)
    with Image.open(dst) as image:
        assert image.size == (280, 160)
        pixels = np.asarray(image.convert("RGB"))
    assert result["verified_exact_text"][0]["exact_text"] == "SALE 30"
    np.testing.assert_array_equal(pixels[0, 0], (52, 51, 79))
    assert pixels[60:80, 70:170, 0].max() >= 230


def test_selected_face_overlap_fails_before_any_neural_export(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    src, dst = tmp_path/"source.png", tmp_path/"blocked.png"
    Image.new("RGB", (140, 80), (52, 51, 79)).save(src)
    settings = V21Settings(
        ai_scale=2, face_protection=True, face_mode="recover",
        face_regions=((.2, .2, .8, .8),),
        v211_verified_text_regions=(region(),),
    )
    with pytest.raises(ValueError, match="ทับใบหน้า"):
        adapter_with_stub().process(src, dst, settings, use_ai=True)
    assert not dst.exists()
