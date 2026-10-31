"""Real V2-weight benchmark: LR-source-constrained ink colour versus V2.

The actual shop requirement is better readable, flat-colour text at print
resolution with zero damage to photos, faces and transparent PNGs. Objective
PSNR/SSIM on a native independent HR reference is ONLY an initial research
gate, not certification. There is no external user/customer content.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from tools.v211_real_dual_model_qa import _basic_sr_import_compat
from tools.v211_ink_real_v2_qa import (
    independent_hr, low_res_degradation, quality
)



def thai_reference(subject):
    """Native-HR Thai pixels are drawn FIRST with real RAQM Thai shaping.

    Pure research samples with correctly specified source strings, not OCR.
    These NEVER replace a customer's image or prove exact text recognition.
    """
    import subprocess
    from PIL import ImageDraw, ImageFont

    if subject not in ("thai_thick", "thai_thin", "thai_fx_gradient"):
        raise ValueError(subject)
    font_file = subprocess.check_output(
        ["fc-match", "-f", "%{file}", "Noto Sans Thai"], text=True
    ).strip()
    if "NotoSansThai" not in Path(font_file).name:
        raise RuntimeError("Real Thai benchmark requires NotoSansThai")
    if not ImageFont.core.HAVE_RAQM:
        raise RuntimeError("Real Thai benchmark requires RAQM shaping")
    w, h = 576, 192
    bg = ((30, 36, 61) if subject == "thai_thin" else (62, 58, 86))
    caption = {
        "thai_thick": "ซื้อ ชื่อ โปรโมชั่น",
        "thai_thin": "ชื่อ ซื้อ 39 บาท",
        "thai_fx_gradient": "โปรโมชั่น",
    }[subject]
    font_size = 22 if subject == "thai_thin" else 40
    font = ImageFont.truetype(
        font_file, font_size, layout_engine=ImageFont.Layout.RAQM
    )
    origin = (24, 57)
    art = Image.new("RGB", (w, h), bg)
    painter = ImageDraw.Draw(art)
    if subject == "thai_fx_gradient":
        # Preserve deliberately multicolour, stylized Thai glyphs. First draw
        # an outside-only gold outline, then fill from a separate AA text mask.
        painter.text(origin, caption, font=font,
                     fill=(243, 185, 21), stroke_width=3,
                     stroke_fill=(243, 185, 21))
        ink_mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(ink_mask).text(
            origin, caption, font=font, fill=255
        )
        ramp = np.empty((h, w, 3), dtype=np.uint8)
        ramp[..., 0] = np.linspace(145, 247, w).astype(np.uint8)
        ramp[..., 1] = 30
        ramp[..., 2] = 38
        art.paste(Image.fromarray(ramp), (0, 0), ink_mask)
    else:
        painter.text(origin, caption, font=font, fill=(243, 27, 29))
    return np.asarray(art).copy()


def run(destination=Path("v211-source-ink-real-v2-proof")):
    _basic_sr_import_compat()
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.v21_graphics_ai import V21Settings
    from signprint_ai.v211_source_guided_ink import restore_source_guided_ink

    adapter = NiyomSilpCoreAdapter()
    if not adapter.selected_model_available("real_esrgan"):
        raise RuntimeError("Missing pinned official V2 RealESRGAN checkpoint")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    baseline_settings = V21Settings(
        ai_scale=2, dpi=300, color_mode="RGB", resize_mode="stretch",
        device="cpu", face_protection=False,
        v21_v2_quality_baseline=True, v211_source_guided_ink=False,
        v211_ink_geometry=False,
    )
    # The released app deliberately rejects the unapproved Source-Ink flag.
    # Research must not bypass that safety gate by changing production code.
    # Instead run the official V2 model once, and apply an isolated local
    # postprocess to its final output for A/B evidence only.
    trials = {}
    for subject in ("letters", "blocks", "curves", "photo_control",
                    "thai_thick", "thai_thin", "thai_fx_gradient"):
        folder = destination / subject
        folder.mkdir(parents=True, exist_ok=True)
        truth = np.ascontiguousarray(
            thai_reference(subject) if subject.startswith("thai_")
            else independent_hr(subject)
        )
        source = folder / "LOW_RES_DEGRADED.png"
        Image.fromarray(truth).save(folder / "TRUE_HIGH_RES_REFERENCE.png")
        Image.fromarray(low_res_degradation(truth)).save(source)
        baseline_path = folder / "V2_original.png"
        research_path = folder / "V211_V2_SourceGuided.png"
        old = adapter.process(
            source, baseline_path, baseline_settings, use_ai=True
        )
        with Image.open(baseline_path) as image, Image.open(source) as original:
            baseline = np.asarray(image.convert("RGB")).copy()
            result, audit = restore_source_guided_ink(image, original)
            # Diagnostic proof, NOT an operator export or a shipped feature.
            result.save(research_path, dpi=image.info.get("dpi", (300, 300)))
            revised = np.asarray(result.convert("RGB")).copy()
        old_psnr, old_ssim = quality(truth, baseline)
        new_psnr, new_ssim = quality(truth, revised)
        trials[subject] = {
            "v2_model": old.get("model"),
            "assisted_v2_model": old.get("model"),
            "isolated_unapproved_postprocess": True,
            "source_ink_audit": audit,
            "native_hr_reference": True,
            "v2_psnr_db": old_psnr,
            "source_ink_psnr_db": new_psnr,
            "psnr_gain_db": round(new_psnr-old_psnr, 4),
            "v2_ssim": old_ssim,
            "source_ink_ssim": new_ssim,
            "ssim_gain": round(new_ssim-old_ssim, 5),
            "pixel_exact": bool(np.array_equal(baseline, revised)),
            "real_thai_glyph_and_print_certified": False,
        }
        (folder / "METRICS.json").write_text(
            json.dumps(trials[subject], ensure_ascii=False, indent=2),
            encoding="utf8"
        )
    screen = bool(
        trials["letters"]["psnr_gain_db"] >= .7
        and trials["letters"]["ssim_gain"] >= 0
        and all(trials[k]["pixel_exact"] for k in
                ("blocks", "curves", "photo_control"))
        # Genuine Thai pixels from the source font; fail the experimental
        # research gate for harmful changes, especially thin tone marks.
        and trials["thai_thick"]["psnr_gain_db"] >= .25
        and trials["thai_thick"]["ssim_gain"] >= 0
        and all(trials[k]["psnr_gain_db"] >= -.02
                and trials[k]["ssim_gain"] >= -.0002
                for k in ("thai_thin", "thai_fx_gradient"))
    )
    report = {
        "model": "Approved V2 RealESRGAN_x4plus + LR source-guided ink",
        "real_weight_inference": True,
        "production_app_source_ink_still_blocked": True,
        "native_hr_thai_text_rendered_before_degradation": True,
        "known_text_no_ocr_or_generated_glyphs": True,
        "provisional_text_colour_screen": screen,
        "quality_release_approved": False,
        "remaining": ["human review of actual Thai diacritics", "letter topology",
                      "PNG/TIFF with AI GPU", "large vinyl prints",
                      "GFPGAN face identity", "MainTop RIP"],
        "trials": trials,
    }
    (destination/"SUMMARY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
