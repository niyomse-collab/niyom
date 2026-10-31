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
    for subject in ("letters", "blocks", "curves", "photo_control"):
        folder = destination / subject
        folder.mkdir(parents=True, exist_ok=True)
        truth = np.ascontiguousarray(independent_hr(subject))
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
    )
    report = {
        "model": "Approved V2 RealESRGAN_x4plus + LR source-guided ink",
        "real_weight_inference": True,
        "production_app_source_ink_still_blocked": True,
        "provisional_text_colour_screen": screen,
        "quality_release_approved": False,
        "remaining": ["actual Thai diacritics", "letter topology",
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
