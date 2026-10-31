"""Real photographic A/B: NAFNet GoPro deblur -> V2 vs V2 alone.

Uses skimage's NASA astronaut sample as independent photographic high-res
reference (never customer artwork) with deterministic motion degradation.
Records raw NAFNet, guarded mask, final V2 output separately to locate where
any quality gain is lost. NO subjective identity/print certification.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage import data
from skimage.metrics import structural_similarity

from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v211_nafnet_deblur import (
    NAFNetGoProDeblurrer, blend_photo_deblur,
    verify_nafnet_checkpoint, nafnet_checkpoint_path
)
from tools.v211_nafnet_real_qa import degrade_blurred
from tools.v211_generate_ab import run_pair
from tools.v211_true_hr_benchmark import _psnr
from tools.v211_real_dual_model_qa import _basic_sr_import_compat


def _photo_hr():
    # NASA astronaut example bundled with scikit-image. True photographic
    # content exists at 512px, resized here to 384px BEFORE 2x degradation.
    return np.asarray(
        Image.fromarray(data.astronaut(), "RGB").resize(
            (384, 384), Image.Resampling.LANCZOS)
    ).copy()


def _ssim(reference, candidate):
    return float(structural_similarity(
        reference, candidate, channel_axis=2, data_range=255
    ))


def run(output=Path("v211-nafnet-photo-proof")):
    _basic_sr_import_compat()
    verify_nafnet_checkpoint(nafnet_checkpoint_path())
    engine = NiyomSilpCoreAdapter()
    if not engine.selected_model_available("v2_nafnet_deblur"):
        raise RuntimeError("Missing V2/NAFNet checkpoints")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    hr = _photo_hr()
    low_clean = np.asarray(
        Image.fromarray(hr).resize((192, 192), Image.Resampling.LANCZOS)
    ).copy()
    low_blurred = degrade_blurred(hr,blur=9,noise=2,angle=25)
    Image.fromarray(hr).save(output/"PHOTO_NATIVE_HR_REFERENCE.png")
    Image.fromarray(low_clean).save(output/"PHOTO_LOWRES_CLEAN.png")
    source = output/"PHOTO_LOWRES_BLURRED.png"
    Image.fromarray(low_blurred).save(source)

    device = engine.engine_manager.device_manager.get_default_device()
    candidate = NAFNetGoProDeblurrer(device)
    raw = candidate.denoise_tile(low_blurred)
    guarded = blend_photo_deblur(low_blurred, raw, strength=.85)
    Image.fromarray(raw).save(output/"NAFNet_RAW_1x.png")
    Image.fromarray(guarded).save(output/"NAFNet_GUARDED_1x.png")
    low_scores={
        "blurred_source_psnr_db":round(_psnr(low_clean,low_blurred),4),
        "raw_nafnet_psnr_db":round(_psnr(low_clean,raw),4),
        "guarded_nafnet_psnr_db":round(_psnr(low_clean,guarded),4),
        "guarded_change_pct_gt3":round(float(
            (np.max(np.abs(guarded.astype(np.int16)-low_blurred.astype(np.int16)),axis=2)>3).mean()*100),4)
    }
    compare=run_pair(
        source,output,adapter=engine,scale=2,dpi=300,device="cpu",
        assist_model="v2_nafnet_deblur"
    )
    with Image.open(output/"V2_reference.png") as image:
        v2=np.asarray(image.convert("RGB")).copy()
    with Image.open(output/"V211_V2_plus_NAFNet.png") as image:
        assisted=np.asarray(image.convert("RGB")).copy()
    output_scores={
        "v2_psnr_db":round(_psnr(hr,v2),4),
        "assisted_psnr_db":round(_psnr(hr,assisted),4),
        "v2_ssim":round(_ssim(hr,v2),5),
        "assisted_ssim":round(_ssim(hr,assisted),5),
    }
    output_scores["psnr_gain_db"]=round(output_scores["assisted_psnr_db"]-output_scores["v2_psnr_db"],4)
    output_scores["ssim_gain"]=round(output_scores["assisted_ssim"]-output_scores["v2_ssim"],5)
    # The mixed-signage blend was deliberately conservative but discarded
    # much of the raw NAFNet denoising/deblurring advantage. A separate
    # unexposed photo-only candidate transfers the actual 1x model output,
    # without applying it to artwork containing letters or logos.
    photo_only_dir = output / "photo_only_candidate"
    photo_only_comparison = run_pair(
        source, photo_only_dir, adapter=engine, scale=2, dpi=300,
        device="cpu", assist_model="v2_nafnet_photo_only"
    )
    with Image.open(photo_only_dir/"V211_V2_plus_NAFNet_PhotoOnly.png") as image:
        raw_photo_final = np.asarray(image.convert("RGB")).copy()
    full_output_scores = {
        "psnr_db": round(_psnr(hr, raw_photo_final),4),
        "ssim": round(_ssim(hr, raw_photo_final),5),
    }
    full_output_scores["psnr_gain_vs_v2_db"] = round(
        full_output_scores["psnr_db"] - output_scores["v2_psnr_db"], 4
    )
    full_output_scores["ssim_gain_vs_v2"] = round(
        full_output_scores["ssim"] - output_scores["v2_ssim"], 5
    )
    full_output_scores["provisional_photo_only_gain"] = bool(
        full_output_scores["psnr_gain_vs_v2_db"] >= 2.0
        and full_output_scores["ssim_gain_vs_v2"] >= .04
    )
    full_output_scores["full_photo_only_not_for_text_or_logos"] = True

    verdict={
        "photo_sample":"skimage astronaut NASA (no customer content)",
        "source_model_path":"NAFNet GoPro width64 1x -> Real-ESRGAN V2 2x",
        "native_photographic_hr":True,
        "low_res_nafnet_ablation":low_scores,
        "final_hr_comparison":output_scores,
        "raw_photo_only_candidate":full_output_scores,
        "raw_photo_only_model":photo_only_comparison["processing"]["assisted_model"],
        "provisional_photo_gain":bool(output_scores["psnr_gain_db"]>=1.0
                                       and output_scores["ssim_gain"]>=0),
        "faces_or_print_certified":False,
        "weights_commercial_redistribution_cleared":False
    }
    (output/"PHOTO_QA.json").write_text(
        json.dumps(verdict,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(verdict,indent=2,ensure_ascii=False))
    return verdict


if __name__=="__main__":
    run()
