"""Research-only REAL NAFNet-GoPro and V2 image enhancement quality screen.

The true-HR reference is rendered first, then downsampled with deliberately
introduced motion blur. Compare original V2 RealESRGAN 2x and NAFNet 1x→V2
2x against the same *independent* HR reference. Photos and graphics measured
separately. The test records even bad results; success of inference is NOT
permission to package, sell, or assert a perceptual quality leap.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v211_nafnet_deblur import (
    nafnet_checkpoint_path, verify_nafnet_checkpoint, NAFNET_SHA256
)
from tools.v211_generate_ab import run_pair
from tools.v211_true_hr_benchmark import (
    make_ground_truth, evaluate_true_hr
)
from tools.v211_real_dual_model_qa import _basic_sr_import_compat


def degrade_blurred(hr, blur=9, noise=2, angle=0, seed=211):
    if blur < 3 or blur%2 != 1:
        raise ValueError("Motion kernel must be odd and >=3")
    h,w=hr.shape[:2]
    if h%2 or w%2:raise ValueError("Reference must have even dimensions")
    lr=np.asarray(Image.fromarray(hr, "RGB").resize(
        (w//2,h//2),Image.Resampling.LANCZOS)).copy()
    k=np.zeros((blur,blur),np.float32)
    cv2.line(k, (0,blur//2), (blur-1,blur//2), 1.0, 1)
    k=cv2.warpAffine(
        k, cv2.getRotationMatrix2D((blur-1)/2*(1,1), angle, 1),
        (blur,blur), flags=cv2.INTER_LINEAR)
    k/=k.sum()
    degraded=cv2.filter2D(lr, -1, k, borderType=cv2.BORDER_REFLECT)
    rng=np.random.default_rng(seed)
    noisy=degraded.astype(np.float32)+rng.normal(0,noise,degraded.shape)
    return np.clip(np.rint(noisy),0,255).astype(np.uint8)


def run(output=Path("v211-nafnet-true-hr-proof")):
    _basic_sr_import_compat()
    verify_nafnet_checkpoint(nafnet_checkpoint_path())
    engine=NiyomSilpCoreAdapter()
    if not engine.selected_model_available("v2_nafnet_deblur"):
        raise RuntimeError("Both V2 RealESRGAN and pinned NAFNet weights required")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    hr=make_ground_truth((192,192))
    scenarios=(("motion_horizontal",9,0,2),("motion_diagonal",11,35,2),
               ("clean_control",3,0,0))
    results={}
    for name,kernel,angle,noise in scenarios:
        folder=output/name
        folder.mkdir(parents=True,exist_ok=True)
        low=(np.asarray(Image.fromarray(hr).resize(
            (96,96),Image.Resampling.LANCZOS)).copy()
             if name=="clean_control" else
             degrade_blurred(hr,kernel,noise,angle))
        Image.fromarray(hr).save(folder/"TRUE_HIGH_RES_REFERENCE.png")
        source=folder/"DEGRADED_SOURCE.png"
        Image.fromarray(low).save(source)
        comparison=run_pair(source,folder,adapter=engine,scale=2,dpi=300,
                            device="cpu",assist_model="v2_nafnet_deblur")
        with Image.open(folder/"V2_reference.png") as base_img:
            base=np.asarray(base_img.convert("RGB")).copy()
        with Image.open(folder/"V211_V2_plus_NAFNet.png") as rest_img:
            restored=np.asarray(rest_img.convert("RGB")).copy()
        score=evaluate_true_hr(hr,base,restored)
        score["original_source"]=name
        score["real_models"]={
            "v2":comparison["processing"]["v2_model"],
            "deblur_v2":comparison["processing"]["assisted_model"]}
        score["source_reference_not_bicubic_proxy"]=True
        score["copyright_weights_not_redistributed"]=True
        results[name]=score
        (folder/"TRUE_HR_METRICS.json").write_text(
            json.dumps(score,indent=2,ensure_ascii=False),encoding="utf8")
    summary={
        "model":"NAFNet GoPro width64 + V2 Real-ESRGAN 2x",
        "nafnet_checkpoint_sha256":NAFNET_SHA256,
        "real_weight_inference_passed":True,
        "photo_recovery_and_graphic_metrics":results,
        "provisional_release_quality":bool(
            results["motion_horizontal"]["provisional_quality_screen_pass"]
            and results["motion_diagonal"]["provisional_quality_screen_pass"]
            and results["clean_control"]["overall"]["gain_db"]>=-0.1),
        "real_print_portrait_thai_text_certified":False,
        "commercial_weight_redistribution_certified":False}
    (output/"SUMMARY.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf8")
    print(json.dumps({
        "real_weight_inference_passed":True,
        "case_gains":{name:{key:metric["gain_db"]
                            for key,metric in result.items()
                            if isinstance(metric,dict) and "gain_db" in metric}
                      for name,result in results.items()},
        "provisional_release_quality":summary["provisional_release_quality"],
        "portrait_text_print_certified":False,
    },indent=2))
    return summary


if __name__=="__main__":
    run()
