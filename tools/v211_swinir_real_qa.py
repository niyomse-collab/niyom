"""Real checkpoint A/B experiment: SwinIR denoise -> V2 vs unaltered V2.

Creates reproducible synthetic photo with known ground truth + Gaussian noise.
Tests SwinIR 1x restoration *before* V2, not a HAT edge-saturation trick.
No private photos, unlicensed checkpoints, or claims of print-quality acceptance.
"""
from __future__ import annotations
from pathlib import Path
import json
import math

import numpy as np
from PIL import Image, ImageDraw

from tools.v211_real_dual_model_qa import _basic_sr_import_compat
from tools.v211_generate_ab import run_pair
from signprint_ai.v211_swinir_preprocess import (
    SwinIRColorDenoiser, SWINIR_SHA256, verify_swinir_checkpoint,
    swinir_checkpoint_path, blend_pre_restoration
)
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter


def synthetic_reference_and_noise(size=(64, 64), sigma=15):
    """Varying photo-like ground-truth colour gradients and crisp sign geometry."""
    width, height = size
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    rgb = np.stack((
        65 + 1.4 * xx + .15 * yy + 13 * np.sin(yy / 8),
        40 + 1.1 * yy + .32 * xx,
        92 + .4 * xx + .55 * yy + 10 * np.cos(xx / 6)
    ), axis=2)
    truth = Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8), "RGB")
    painter = ImageDraw.Draw(truth)
    painter.rectangle((3, 4, 29, 18), fill=(247, 20, 33))
    painter.rectangle((31, 4, 59, 18), fill=(24, 65, 238))
    painter.line((3, 24, width-4, 24), fill=(245, 242, 230), width=2)
    painter.arc((12, 27, 53, 58), 10, 260, fill=(12, 15, 18), width=2)
    ground_truth = np.asarray(truth).copy()
    rng = np.random.default_rng(2112026)
    distorted = np.rint(np.clip(
        ground_truth.astype(np.float32) + rng.normal(0, sigma, ground_truth.shape),
        0, 255
    )).astype(np.uint8)
    return ground_truth, distorted


def _psnr(reference: np.ndarray, candidate: np.ndarray, mask=None):
    if reference.shape != candidate.shape:
        raise ValueError("PSNR requires identical image sizes")
    diff = (reference.astype(np.float64) - candidate.astype(np.float64)) ** 2
    if mask is not None:
        diff = diff[mask]
    mse = float(np.mean(diff))
    return float("inf") if mse <= 0 else 10 * math.log10(255 * 255 / mse)


def run(output_dir=Path("v211-swinir-proof")):
    _basic_sr_import_compat()
    checkpoint = swinir_checkpoint_path()
    verify_swinir_checkpoint(checkpoint)
    adapter = NiyomSilpCoreAdapter()
    if not adapter.selected_model_available("v2_swinir_pre"):
        raise RuntimeError("Real V2 and verified SwinIR weights required")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean, noisy = synthetic_reference_and_noise()
    source = output_dir / "photo_noise_input.png"
    Image.fromarray(clean).save(output_dir / "photo_reference_clean.png")
    Image.fromarray(noisy).save(source)

    denoiser = SwinIRColorDenoiser(
        adapter.engine_manager.device_manager.get_default_device()
    )
    raw_denoised = denoiser.denoise_tile(noisy)
    selected_denoised = blend_pre_restoration(noisy, raw_denoised, .70)
    Image.fromarray(selected_denoised).save(output_dir / "pre_denoised.png")

    # Compare a known photographic interior away from synthetic text/sign edges.
    roi = np.zeros(clean.shape[:2], dtype=bool)
    roi[30:62, 3:58] = True
    before_psnr = _psnr(clean, noisy, roi)
    after_psnr = _psnr(clean, selected_denoised, roi)
    print("Source photo ROI PSNR noisy:", round(before_psnr, 3))
    print("Source photo ROI PSNR restored:", round(after_psnr, 3))
    if not after_psnr > before_psnr + .10:
        raise AssertionError(
            "SwinIR did not measurably restore the known photographic reference; "
            "do not claim visible quality improvement"
        )

    comparison = run_pair(
        source, output_dir, adapter=adapter, device="cpu",
        scale=2, dpi=300, assist_model="v2_swinir_pre"
    )
    if comparison["processing"]["v2_model"] != "RealESRGAN_x4plus":
        raise AssertionError("V2 baseline was not used")
    if comparison["processing"]["assisted_model"] != "V2 RealESRGAN_x4plus + SwinIR pre-denoise":
        raise AssertionError("Both real models were not used in the assisted path")
    summary = {
        "model": "SwinIR colour denoise 15 -> V2 Real-ESRGAN",
        "checkpoint_sha256": SWINIR_SHA256,
        "real_checkpoint_inference": True,
        "photo_source_roi_psnr_before": round(before_psnr, 4),
        "photo_source_roi_psnr_after": round(after_psnr, 4),
        "source_roi_psnr_gain_db": round(after_psnr - before_psnr, 4),
        "v2_vs_assisted": comparison,
        "subjective_quality_certified": False,
        "portrait_identity_certified": False,
        "thai_text_certified": False,
        "physical_print_certified": False,
        "commercial_checkpoint_redistribution_approved": False,
    }
    (output_dir / "SWINIR_REAL_MODEL_QA.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "source_roi_psnr_gain_db": summary["source_roi_psnr_gain_db"],
        "real_checkpoint_inference": True,
        "v2_vs_assisted": comparison["overall"],
        "quality_certified": False
    }, indent=2))
    return summary


if __name__ == "__main__":
    run()
