"""Real V2 neural baseline vs user-verified exact-font Thai and English text.

This tests a materially different workflow than trying to hallucinate glyphs
from destroyed source pixels: the print shop already HAS the correct Unicode
customer text and matching font. The faithful text is drawn AFTER V2 SR at the
target resolution. Image geometry outside approved ROIs remains V2 pixel-exact.

The golden reference intentionally uses the same explicitly supplied strings
and matching fonts, so the result demonstrates human-verified re-rendering,
NOT automatic OCR/text reconstruction, and not a general AI quality leap.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from signprint_ai.v211_verified_text import (
    VerifiedTextRegion, exact_text_overlay
)
from tools.v211_real_dual_model_qa import _basic_sr_import_compat
from tools.v211_ink_real_v2_qa import quality


def _find_thai_font() -> str:
    candidates = (
        "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
        "/usr/share/fonts/truetype/thai-tlwg/Garuda.ttf",
        "/usr/share/fonts/opentype/tlwg/Garuda.otf",
        "/usr/share/fonts/truetype/thai-tlwg/TlwgTypist.ttf",
    )
    for font in candidates:
        if Path(font).is_file():
            return font
    resolved = subprocess.check_output(
        ["fc-match", "-f", "%{file}", ":lang=th"], text=True
    ).strip()
    if not Path(resolved).is_file():
        raise RuntimeError("Thai font required for independent rendered proof")
    return resolved


def _find_latin_font() -> str:
    for font in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(font).is_file():
            return font
    raise RuntimeError("Need installed Latin font for reproducible source sign")


def build_truth():
    thai = _find_thai_font()
    latin = _find_latin_font()
    canvas = Image.new("RGBA", (384, 328), (57, 55, 83, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((250, 15, 370, 84), fill=(244, 15, 31, 255))
    draw.rectangle((25, 15, 140, 84), fill=(25, 68, 235, 255))
    draw.line((24, 97, 364, 97), fill=(255, 255, 247, 255), width=5)
    regions = (
        VerifiedTextRegion(
            16, 135, 352, 70, "ซื้อ ชื่อ โปรโมชั่น", thai, 46,
            (240, 242, 245), "center", "replace_flat"
        ),
        VerifiedTextRegion(
            18, 234, 255, 66, "SALE 30", latin, 46,
            (245, 25, 37), "center", "replace_flat"
        ),
    )
    # The reference is uncompressed final-resolution typography with exact
    # Unicode and font; no neural model has ever distorted these glyphs.
    for region in regions:
        overlay, _ = exact_text_overlay(canvas.size, region)
        canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB"), regions


def _roi_psnr(truth, candidate, rect):
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    a = truth[y:y+h, x:x+w].astype(np.float64)
    b = candidate[y:y+h, x:x+w].astype(np.float64)
    mse = float(np.mean((a-b)**2))
    return float("inf") if mse == 0 else round(
        10*np.log10(255.0**2/mse), 4
    )


def run(out=Path("v211-verified-text-real-v2-proof")):
    _basic_sr_import_compat()
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.v21_graphics_ai import V21Settings

    engine = NiyomSilpCoreAdapter()
    if not engine.selected_model_available("real_esrgan"):
        raise RuntimeError("Missing original official RealESRGAN_x4plus weight")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    reference, regions = build_truth()
    truth = np.asarray(reference).copy()
    reference.save(out/"NATIVE_HIGH_RES_TEXT_REFERENCE.png")
    lr = np.asarray(reference.resize(
        (192, 164), Image.Resampling.LANCZOS
    ), dtype=np.uint8)
    lr = cv2.GaussianBlur(lr, (0, 0), .6)
    noise = np.random.default_rng(202611).normal(0, .8, lr.shape)
    source_pixels = np.rint(np.clip(
        lr.astype(np.float32)+noise, 0, 255
    )).astype(np.uint8)
    source = out/"DEGRADED_LOW_RES_SOURCE.png"
    Image.fromarray(source_pixels).save(source)

    common = V21Settings(
        ai_scale=2, dpi=300, device="cpu", color_mode="RGB",
        resize_mode="stretch", face_protection=False,
        v21_v2_quality_baseline=True, v211_ink_geometry=False,
        v211_source_guided_ink=False,
    )
    baseline_path = out/"APPROVED_V2.png"
    rebuilt_path = out/"V211_VERIFIED_EXACT_TEXT.png"
    baseline_meta = engine.process(source, baseline_path, common, use_ai=True)
    rebuilt_meta = engine.process(
        source, rebuilt_path,
        replace(common, v211_verified_text_regions=regions),
        use_ai=True
    )
    with Image.open(baseline_path) as image:
        baseline = np.asarray(image.convert("RGB")).copy()
    with Image.open(rebuilt_path) as image:
        rebuilt = np.asarray(image.convert("RGB")).copy()
    baseline_psnr, baseline_ssim = quality(truth, baseline)
    updated_psnr, updated_ssim = quality(truth, rebuilt)

    untouched = np.ones(truth.shape[:2], bool)
    roi_scores = {}
    for region in regions:
        untouched[region.y:region.y+region.height,
                  region.x:region.x+region.width] = False
        roi_scores[region.text] = {
            "v2_psnr_db": _roi_psnr(truth, baseline, region),
            "verified_text_psnr_db": _roi_psnr(truth, rebuilt, region),
        }
        roi_scores[region.text]["gain_db"] = round(
            roi_scores[region.text]["verified_text_psnr_db"]
            - roi_scores[region.text]["v2_psnr_db"], 4
        )
    untouched_exact = bool(np.array_equal(
        baseline[untouched], rebuilt[untouched]
    ))
    report = {
        "method": "exact supplied text + installed RAQM font, NOT automatic OCR",
        "actual_official_v2_neural_inference": True,
        "matching_native_high_res_reference": True,
        "rgb_dimensions": [384, 328],
        "input_degraded_dimensions": [192, 164],
        "v2_psnr_db": baseline_psnr,
        "exact_text_psnr_db": updated_psnr,
        "psnr_gain_db": round(updated_psnr-baseline_psnr, 4),
        "v2_ssim": baseline_ssim,
        "exact_text_ssim": updated_ssim,
        "outside_selected_text_pixel_identical_to_v2": untouched_exact,
        "text_roi_scores": roi_scores,
        "exact_text_audits": rebuilt_meta["verified_exact_text"],
        "general_automatic_ai_typography_quality_certified": False,
        "user_selected_font_and_text_required": True,
        "real_printer_print_certified": False,
    }
    (out/"SUMMARY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not untouched_exact:
        raise AssertionError("Verified text changed pixels outside chosen ROIs")
    return report


if __name__ == "__main__":
    run()
