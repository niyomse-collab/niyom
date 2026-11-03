"""Real-weight A/B benchmark against TRUE high-resolution synthetic ground truth.

Unlike a bicubic-upscaled low-resolution input, this independent reference is
*drawn at target resolution first*, then degraded to produce the LR source.
Run BOTH V2 and V2+SwinIR through the production adapter, with matching
settings. A completed benchmark does not certify restoration quality.

The reference includes crisp subpixel-style graphic edges and photographic
texture. Model checkpoints and actual inference are managed by the opt-in
research workflow; never upload customer artwork or commercial model weights.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from tools.v211_generate_ab import run_pair


def make_ground_truth(size=(192, 192)):
    """Reproducible high-resolution artwork with real high-frequency detail."""
    width, height = size
    if width < 96 or height < 96 or width % 2 or height % 2:
        raise ValueError("True HR reference dimensions must be even and >=96")
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    rgb = np.stack((
        49 + 0.43 * xx + .17 * yy + 17 * np.sin(yy / 11.0),
        43 + .31 * yy + 0.15 * xx + 11 * np.cos(xx / 15.0),
        96 + 0.21 * xx + 0.19 * yy,
    ), axis=-1)
    # The lower-left region represents fine-grained photographic material,
    # rather than pretending that a sharp flat logo should be denoised.
    rng = np.random.default_rng(202611)
    texture = rng.normal(0, 5, (height, width, 1))
    photo_mask = (yy >= height * .52) & (xx < width * .53)
    rgb += photo_mask[..., None] * texture
    image = Image.fromarray(np.uint8(np.clip(np.rint(rgb), 0, 255)), "RGB")
    d = ImageDraw.Draw(image)
    d.rectangle((10, 14, width//2-4, height//3), fill=(245, 26, 36))
    d.rectangle((width//2+4, 14, width-10, height//3), fill=(19, 70, 238))
    d.line((10, height//2-11, width-12, height//2-11), fill=(246, 248, 241), width=3)
    d.arc((int(width*.2), int(height*.43), int(width*.83), int(height*.93)),
          14, 295, fill=(12, 13, 20), width=4)
    # Fine vector-like letters/contours: exact black/white reference.
    d.rectangle((width//2+9, int(height*.66), width-12, int(height*.69)),
                fill=(250, 240, 45))
    for i in range(3):
        d.line((width//2+13, int(height*.75)+i*6,
                width-17, int(height*.75)+i*6), fill=(18, 20, 35), width=2)
    return np.asarray(image, dtype=np.uint8)


def degrade_to_low_resolution(high_res, sigma=15, seed=211):
    """Make the LR source AFTER saving the HR truth; no HR interpolation proxy."""
    if (high_res.ndim != 3 or high_res.shape[2] != 3
            or high_res.dtype != np.uint8):
        raise ValueError("Ground truth must be uint8 RGB")
    h, w = high_res.shape[:2]
    if (h % 2) or (w % 2):
        raise ValueError("HR dimensions must be divisible by scale 2")
    down = np.asarray(Image.fromarray(high_res).resize(
        (w // 2, h // 2), Image.Resampling.LANCZOS), dtype=np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, sigma, down.shape)
    return np.uint8(np.clip(np.rint(down + noise), 0, 255))


def _psnr(reference, candidate, mask=None):
    if reference.shape != candidate.shape:
        raise ValueError("True-HR metric requires equal dimensions")
    a = reference.astype(np.float64)
    b = candidate.astype(np.float64)
    difference = (a-b)**2
    if mask is not None:
        if mask.shape != reference.shape[:2] or not mask.any():
            raise ValueError("ROI mask empty or wrong shape")
        difference = difference[mask]
    mse = float(difference.mean())
    return float("inf") if mse == 0 else float(10*np.log10(255.0**2/mse))


def _regions(hr):
    """Regions derived ONLY from reference layout, never predicted pixels."""
    h, w = hr.shape[:2]
    photo = np.zeros((h, w), dtype=bool)
    photo[int(h*.57):int(h*.95), int(w*.04):int(w*.47)] = True
    graphic = np.zeros_like(photo)
    graphic[10:int(h*.42), 8:w-8] = True
    graphic[int(h*.43):int(h*.95), int(w*.51):w-8] = True
    gx = cv2.Sobel(hr.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(hr.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    edge = np.sqrt(gx*gx + gy*gy).max(axis=2) > 120
    ink_edges = edge & graphic
    flat_ink = graphic & ~cv2.dilate(
        ink_edges.astype(np.uint8), np.ones((5, 5), np.uint8)
    ).astype(bool)
    return {"overall": np.ones((h,w), dtype=bool),
            "photo_texture": photo,
            "graphic_edges": ink_edges,
            "flat_ink": flat_ink}


def evaluate_true_hr(hr, v2, assisted):
    """Objective comparison against actual HR reference, not invented pixels."""
    masks = _regions(hr)
    result = {}
    for label, mask in masks.items():
        baseline = _psnr(hr, v2, mask)
        candidate = _psnr(hr, assisted, mask)
        result[label] = {
            "pixels": int(mask.sum()),
            "v2_psnr_db": round(baseline, 4),
            "assisted_psnr_db": round(candidate, 4),
            "gain_db": round(candidate - baseline, 4),
        }
    # Provisional screen only: >1 dB overall and >1 dB photo texture,
    # graphic ROI must not regress. Human text/face/print review is STILL
    # mandatory, regardless of this flag.
    result["provisional_quality_screen_pass"] = bool(
        result["overall"]["gain_db"] >= 1.0
        and result["photo_texture"]["gain_db"] >= 1.0
        and result["graphic_edges"]["gain_db"] >= -0.1
        and result["flat_ink"]["gain_db"] >= -0.1
    )
    result["image_quality_certified"] = False
    result["print_or_face_certified"] = False
    result["reference_type"] = "independently rendered synthetic true-HR"
    return result


def run(out=Path("v211-true-hr-proof"), *, adapter=None):
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    source_engine = adapter if adapter is not None else NiyomSilpCoreAdapter()
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    hr = make_ground_truth()
    lr = degrade_to_low_resolution(hr)
    Image.fromarray(hr, "RGB").save(directory/"TRUE_HIGH_RES_REFERENCE.png")
    source = directory/"DEGRADED_LOW_RES_SOURCE.png"
    Image.fromarray(lr, "RGB").save(source)
    report = run_pair(source, directory, adapter=source_engine,
                      scale=2, dpi=300, device="cpu",
                      assist_model="v2_swinir_pre")
    with Image.open(directory/"V2_reference.png") as image:
        v2 = np.asarray(image.convert("RGB")).copy()
    with Image.open(directory/"V211_V2_plus_SwinIR.png") as image:
        assisted = np.asarray(image.convert("RGB")).copy()
    quality = evaluate_true_hr(hr, v2, assisted)
    quality["adapter_output_models"] = report["processing"]
    quality["same_alpha_icc_dpi"] = (
        report["same_alpha"] and report["same_icc"]
        and report["v2_metadata"]["dpi"] == report["super_metadata"]["dpi"]
    )
    (directory/"TRUE_HR_BENCHMARK.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(quality, indent=2, ensure_ascii=False))
    return quality


if __name__ == "__main__":
    run()
