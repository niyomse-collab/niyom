"""Independent real-checkpoint V2 versus V2+flat ink geometry A/B.

This is a research experiment, not a V2.1.1 release or print certification.
High-resolution RGB artwork is independently drawn *first*, then a low-res
source is degraded to emulate the user's blurred print graphics. Both output
routes run the exact production adapter with an official pinned Real-ESRGAN V2
checkpoint. All images are synthetic / public-domain samples, not customer art.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage import data
from skimage.metrics import structural_similarity

from tools.v211_real_dual_model_qa import _basic_sr_import_compat


def independent_hr(subject, side=192):
    if subject == "photo_control":
        image = Image.fromarray(data.astronaut(), "RGB")
        return np.asarray(image.resize((side, side), Image.Resampling.LANCZOS))
    im = Image.new("RGB", (side, side), (62, 58, 86))
    draw = ImageDraw.Draw(im)
    if subject == "blocks":
        draw.rectangle((13, 14, 92, 94), fill=(247, 23, 31))
        draw.rectangle((97, 14, side-13, 94), fill=(14, 61, 244))
        draw.line((15, 116, side-15, 116), fill=(250, 246, 238), width=5)
    elif subject == "curves":
        draw.arc((22, 30, side-21, side-20), 18, 285,
                 fill=(11, 15, 20), width=11)
        draw.line((14, 15, side-14, 15), fill=(245, 187, 18), width=9)
    elif subject == "letters":
        font = ImageFont.load_default(size=29)
        draw.text((10, 43), "PRINT SHOP", font=font, fill=(244, 244, 245))
        draw.text((10, 92), "SALE 30", font=font, fill=(243, 27, 29))
        # Three independent thin marks mimic the geometric failure mode
        # of Thai vowel/tone mark stacks. NOT a Thai OCR/spelling test.
        for i in range(3):
            draw.ellipse((110+i*8, 28-i*2, 112+i*8, 30-i*2),
                         fill=(249, 220, 20))
    else:
        raise ValueError(subject)
    return np.asarray(im)


def low_res_degradation(highres):
    if highres.shape[0] % 2 or highres.shape[1] % 2:
        raise ValueError("True HR dimensions must be divisible by two")
    h, w = highres.shape[:2]
    rgb = np.asarray(
        Image.fromarray(highres).resize((w//2, h//2),
                                        Image.Resampling.LANCZOS)
    ).copy()
    blur = cv2.GaussianBlur(rgb, (0, 0), 0.6)
    noise = np.random.default_rng(12345).normal(0, 1.0, blur.shape)
    return np.rint(np.clip(blur.astype(np.float32)+noise, 0, 255)).astype(np.uint8)


def quality(truth, output):
    if truth.shape != output.shape:
        raise ValueError("Native HR reference / output geometry mismatch")
    mse = np.mean(
        (truth.astype(np.float64)-output.astype(np.float64))**2
    )
    psnr = float("inf") if mse == 0 else float(
        10*np.log10(255**2/mse)
    )
    ssim = float(structural_similarity(
        truth, output, data_range=255, channel_axis=2
    ))
    return round(psnr, 4), round(ssim, 5)


def run(destination=Path("v211-ink-real-v2-proof")):
    _basic_sr_import_compat()
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.v21_graphics_ai import V21Settings
    from signprint_ai.v211_ink_geometry import reconstruct_ink_pixels

    adapter = NiyomSilpCoreAdapter()
    if not adapter.selected_model_available("real_esrgan"):
        raise RuntimeError("Official pinned RealESRGAN_x4plus V2 weights missing")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    baseline_settings = V21Settings(
        ai_scale=2, dpi=300, color_mode="RGB", resize_mode="stretch",
        device="CPU", face_protection=False,
        v21_v2_quality_baseline=True, v211_ink_geometry=False,
    )
    experiment_settings = replace(
        baseline_settings, v211_ink_geometry=True,
        v211_ink_geometry_strength=1.0
    )
    trials = {}
    for subject in ("blocks", "curves", "letters", "photo_control"):
        folder = destination / subject
        folder.mkdir(parents=True, exist_ok=True)
        truth = np.ascontiguousarray(independent_hr(subject))
        source = folder / "LOW_RES_DEGRADED.png"
        Image.fromarray(truth).save(folder / "TRUE_HIGH_RES_REFERENCE.png")
        Image.fromarray(low_res_degradation(truth)).save(source)
        baseline_path = folder / "V2_original.png"
        assisted_path = folder / "V211_V2_plus_InkGeometry.png"
        baseline = adapter.process(
            source, baseline_path, baseline_settings, use_ai=True
        )
        assisted = adapter.process(
            source, assisted_path, experiment_settings, use_ai=True
        )
        with Image.open(baseline_path) as image:
            original = np.asarray(image.convert("RGB")).copy()
        with Image.open(assisted_path) as image:
            enhanced = np.asarray(image.convert("RGB")).copy()
        original_psnr, original_ssim = quality(truth, original)
        enhanced_psnr, enhanced_ssim = quality(truth, enhanced)
        _, geometry = reconstruct_ink_pixels(original)
        pixel_identical = bool(np.array_equal(original, enhanced))
        result = {
            "V2_model": baseline.get("model"),
            "V211_model": assisted.get("model"),
            "native_high_res_reference": True,
            "original_psnr_db": original_psnr,
            "enhanced_psnr_db": enhanced_psnr,
            "gain_psnr_db": round(enhanced_psnr - original_psnr, 4),
            "original_ssim": original_ssim,
            "enhanced_ssim": enhanced_ssim,
            "gain_ssim": round(enhanced_ssim - original_ssim, 5),
            "pixel_identical": pixel_identical,
            "geometry_audit": geometry,
            "text_spelling_certified": False,
            "real_print_certified": False,
        }
        trials[subject] = result
        (folder / "METRICS.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # These research thresholds are PROVISIONAL. Real Thai diacritics,
    # legibility, skin, HDR scenes and print inspection are mandatory.
    screening = bool(
        all(trials[name]["gain_psnr_db"] >= 1.0
            and trials[name]["gain_ssim"] >= 0
            for name in ("blocks", "curves"))
        and trials["letters"]["gain_psnr_db"] >= .25
        and trials["letters"]["gain_ssim"] >= 0
        and trials["photo_control"]["pixel_identical"]
    )
    report = {
        "model": "Approved V2 RealESRGAN_x4plus vs opt-in ink geometry",
        "actual_pretrained_v2_inference": True,
        "provisional_synthetic_geometry_screen_passed": screening,
        "release_quality_certified": False,
        "real_thai_glyph_face_alpha_mainTop_print_certified": False,
        "trials": trials,
    }
    (destination / "SUMMARY.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    run()
