"""V2.1.1 quality safeguards exercised through actual application paths.

These are deterministic regression tests, NOT a claim that the model visually
improves portraits or print. They prevent a known sharp-image regression,
preserve alpha during AI output and forbid export on skipped face Recover.
"""
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from signprint_ai.v211_blur_gate import (
    assess_explicit_photo_blur, select_photo_restoration,
)


@dataclass(frozen=True)
class Experiment:
    v211_photo_model: str = "v2_nafnet_photo_only"
    face_protection: bool = False
    face_mode: str = "recover"
    face_regions: tuple | None = None


def _photolike_source():
    """Color gradients and overlapping natural-looking rounded objects."""
    rng = np.random.default_rng(55)
    yy, xx = np.mgrid[:192, :192]
    out = np.zeros((192, 192, 3), dtype=np.uint8)
    out[..., 0] = np.clip(30 + xx*.25 + yy*.30, 0, 255)
    out[..., 1] = np.clip(60 + xx*.30 + yy*.45, 0, 255)
    out[..., 2] = np.clip(95 + xx*.30 + yy*.25, 0, 255)
    for _ in range(60):
        center = tuple(int(v) for v in rng.integers(0, 192, 2))
        axes = tuple(int(v) for v in rng.integers(5, 42, 2))
        color = tuple(int(v) for v in rng.integers(30, 235, 3))
        cv2.ellipse(out, center, axes, 0, 0, 360, color, -1)
    return out


def _motion_blurred(image):
    kernel = np.zeros((9, 9), dtype=np.float32)
    cv2.line(kernel, (0, 4), (8, 4), 1, 1)
    kernel = cv2.warpAffine(
        kernel, cv2.getRotationMatrix2D((4, 4), 24, 1), (9, 9)
    )
    kernel /= kernel.sum()
    return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT)


def _bright_sign():
    out = np.full((192, 192, 3), (50, 50, 50), dtype=np.uint8)
    out[24:180, 22:96] = (250, 20, 25)
    out[24:180, 97:181] = (20, 70, 250)
    return out


def test_clean_photo_falls_back_to_v2_before_running_nafnet(tmp_path):
    photo = tmp_path / "photo.png"
    Image.fromarray(_photolike_source()).save(photo)
    assert not assess_explicit_photo_blur(_photolike_source()).allow
    chosen, audit = select_photo_restoration(
        Experiment(), photo, use_ai=True, model_scale=2
    )
    assert chosen.v211_photo_model == "real_esrgan"
    assert audit["actual_model"] == "real_esrgan"
    assert "sharp_or_uncertain" in audit["reason"]
    assert audit["automatic_quality_certified"] is False


def test_motion_blurred_photographic_crop_eligible_but_not_certified(tmp_path):
    pixels = _motion_blurred(_photolike_source())
    assert assess_explicit_photo_blur(pixels).allow
    photo = tmp_path / "blurred.png"
    Image.fromarray(pixels).save(photo)
    chosen, audit = select_photo_restoration(
        Experiment(), photo, use_ai=True, model_scale=2
    )
    assert chosen.v211_photo_model == "v2_nafnet_photo_only"
    assert audit["actual_model"] == "v2_nafnet_photo_only"
    assert audit["blur_metrics"]["automatic_quality_certified"] is False


def test_vivid_print_graphics_do_not_enter_photo_only_deblurring(tmp_path):
    sign = tmp_path / "sign.png"
    Image.fromarray(_motion_blurred(_bright_sign())).save(sign)
    model, audit = select_photo_restoration(
        Experiment(), sign, use_ai=True, model_scale=2
    )
    assert model.v211_photo_model == "real_esrgan"
    assert audit["reason"] == "sharp_or_uncertain_input_keep_v2"


def test_rgba_png_never_triggers_photo_only_model(tmp_path):
    rgba = np.zeros((96, 96, 4), np.uint8)
    rgba[20:70, 20:70] = (245, 20, 80, 255)
    src = tmp_path / "transparent_logo.png"
    Image.fromarray(rgba, "RGBA").save(src)
    chosen, audit = select_photo_restoration(
        Experiment(), src, use_ai=True, model_scale=4
    )
    assert chosen.v211_photo_model == "real_esrgan"
    assert audit["reason"] == "transparent_png_or_tiff_keep_v2"


def test_unconfirmed_recover_face_selection_bypasses_experimental_photo_model(tmp_path):
    src = tmp_path / "blurred.png"
    Image.fromarray(_motion_blurred(_photolike_source())).save(src)
    chosen, audit = select_photo_restoration(
        Experiment(face_protection=True, face_mode="recover",
                   face_regions=None),
        src, use_ai=True, model_scale=2
    )
    assert chosen.v211_photo_model == "real_esrgan"
    assert "confirm_detected_faces" in audit["reason"]


def test_confirmed_face_selection_keeps_exact_v2_gfpgan_pass(tmp_path):
    src = tmp_path / "blurred.png"
    Image.fromarray(_motion_blurred(_photolike_source())).save(src)
    chosen, audit = select_photo_restoration(
        Experiment(face_protection=True, face_mode="recover",
                   face_regions=((.3,.2,.7,.75),)),
        src, use_ai=True, model_scale=2
    )
    assert chosen.v211_photo_model == "v2_nafnet_photo_only"
    assert audit["automatic_quality_certified"] is False


class FakeV2:
    def enhance(self, src, dst, *, scale=2, progress_callback=None,
                cancel_check=None):
        with Image.open(src) as im:
            rgb = im.convert("RGB")
            rgb.resize((rgb.width*scale, rgb.height*scale),
                       Image.Resampling.NEAREST).save(dst)
        return {"model": "V2 unit-test stub"}

    def device_name(self):
        return "CPU"


def _adapter():
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.create_job_engine = lambda settings: FakeV2()
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(device_id="cpu")
        ),
    )
    return adapter


def test_real_ai_path_preserves_transparent_png_alpha_after_upscale(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    src, dst = tmp_path / "cutout.png", tmp_path / "result.png"
    rgba = np.zeros((80, 80, 4), np.uint8)
    rgba[..., :3] = (3, 4, 5)
    rgba[18:62, 18:62, :3] = (250, 50, 25)
    rgba[18:62, 18:62, 3] = 255
    Image.fromarray(rgba, "RGBA").save(src)
    engine = _adapter()
    settings = V21Settings(
        ai_scale=2, dpi=300, face_protection=False, color_mode="RGB",
        resize_mode="stretch", v211_photo_model="v2_nafnet_photo_only"
    )
    result = engine.process(src, dst, settings, use_ai=True)
    with Image.open(dst) as image:
        assert image.mode == "RGBA"
        expected = Image.fromarray(rgba, "RGBA").getchannel("A").resize(
            image.size, Image.Resampling.LANCZOS
        )
        np.testing.assert_array_equal(
            np.asarray(image.getchannel("A")), np.asarray(expected)
        )
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((80, 80))[3] == 255
    assert result["photo_preflight"]["actual_model"] == "real_esrgan"
    assert result["photo_preflight"]["reason"] == "transparent_png_or_tiff_keep_v2"


def test_requested_face_recover_fails_before_export_if_gfpgan_skipped(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    src, dst = tmp_path / "portrait.png", tmp_path / "not-exported.png"
    Image.fromarray(_photolike_source()).save(src)
    adapter = _adapter()

    class BrokenFaceRecovery:
        def apply(self, *args, **kwargs):
            raise RuntimeError("GFPGAN model missing")

    adapter.face_module = BrokenFaceRecovery()
    settings = V21Settings(
        ai_scale=2, dpi=300, face_protection=True, face_mode="recover",
        face_regions=((.25, .2, .70, .75),),
        v211_photo_model="real_esrgan",
    )
    with pytest.raises(RuntimeError, match="ฟื้นฟูใบหน้าไม่สำเร็จ"):
        adapter.process(src, dst, settings, use_ai=True)
    assert not dst.exists()



def test_corrupted_gfpgan_face_is_never_exported_after_model_reported_success(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    from signprint_ai.face_module.face_protection import FaceProtectionResult

    src, dst = tmp_path / "portrait.png", tmp_path / "blocked-face.png"
    Image.fromarray(_photolike_source()).save(src)
    adapter = _adapter()

    class DamagedFaceResult:
        def apply(self, image, **kwargs):
            assert kwargs["mode"] == "recover"
            # The neural pass ran, but audit found erased facial detail.
            # No exception was raised by the model; only the final contract
            # may prevent accidental output of an unnatural portrait.
            return image, FaceProtectionResult(
                enabled=True, applied=True, face_count=1, mode="recover",
                face_audit=({
                    "index": 1, "heuristic_pass": False,
                    "reason": "local_face_detail_collapsed", "applied": True,
                },),
            )

    adapter.face_module = DamagedFaceResult()
    settings = V21Settings(
        ai_scale=2, dpi=300, face_protection=True, face_mode="recover",
        face_regions=((.23, .23, .78, .79),),
        v211_photo_model="real_esrgan",
    )
    assert settings.v211_reject_failed_face_audit
    with pytest.raises(RuntimeError, match="ตรวจคุณภาพไม่ผ่าน"):
        adapter.process(src, dst, settings, use_ai=True)
    assert not dst.exists()



def test_rgba_tiff_fit_adds_only_transparent_padding_not_white_or_black(tmp_path):
    from signprint_ai.v21_graphics_ai import V21Settings
    src, dst = tmp_path / "isolated_object.png", tmp_path / "print-cutout.tif"
    rgba = np.zeros((40, 80, 4), dtype=np.uint8)
    rgba[6:34, 8:72] = (215, 35, 28, 255)
    Image.fromarray(rgba, "RGBA").save(src)
    settings = V21Settings(
        ai_scale=2, dpi=100, face_protection=False, color_mode="RGB",
        resize_mode="fit", print_width=4, print_height=4,
        print_unit="in", v211_photo_model="real_esrgan",
    )
    adapter = _adapter()
    adapter.process(src, dst, settings, use_ai=True)
    with Image.open(dst) as result:
        assert result.width == result.height == 400
        assert "A" in result.getbands()
        alpha = np.asarray(result.convert("RGBA").getchannel("A"))
        # Padding outside the contained 2:1 cutout must be truly transparent,
        # not an opaque white/black backdrop from TIFF RGB conversion.
        assert np.all(alpha[:60] == 0)
        assert np.all(alpha[-60:] == 0)
        assert np.any(alpha[170:230, 150:250] == 255)
