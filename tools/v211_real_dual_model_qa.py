"""Research-only, *real weights* V2 + HAT image-processing A/B smoke.

Runs the same NiyomSilp adapter twice on one reproducible synthetic artwork:
  (1) V2 Real-ESRGAN and (2) V2 Real-ESRGAN + HAT detail assist.
No customer assets, auto model downloads, unlicensed weight distribution,
quality certification or production changes. Weights must already exist and
pass their own pinned checksums before this script executes.
"""
from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _basic_sr_import_compat():
    """Map the removed torchvision symbol to the identical current function.

    BasicSR 1.4.2 may import functional_tensor.rgb_to_grayscale, removed by
    newer torchvision builds. The alias is restricted to this research script
    so we do not alter approved V2 application code.
    """
    import torchvision.transforms.functional as functional
    name = "torchvision.transforms.functional_tensor"
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.rgb_to_grayscale = functional.rgb_to_grayscale
        sys.modules[name] = module


def synthetic_sign_photo(size=(48, 40)):
    """Photo-like texture with vivid sign colours, dark fine strokes and noise."""
    width, height = size
    yy, xx = np.mgrid[:height, :width]
    rng = np.random.default_rng(211)
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.clip(42 + xx * 3 + yy // 4, 0, 255)
    rgb[:, :, 1] = np.clip(32 + yy * 4 + xx // 3, 0, 255)
    rgb[:, :, 2] = np.clip(88 + yy * 2, 0, 255)
    rgb = np.clip(
        rgb.astype(np.int16) + rng.integers(-7, 8, size=(height, width, 1)),
        0, 255,
    ).astype(np.uint8)
    image = Image.fromarray(rgb, "RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((3, 4, 29, 18), fill=(248, 20, 35))
    draw.rectangle((30, 4, 44, 18), fill=(15, 85, 245))
    draw.line((2, 23, width - 3, 23), fill=(250, 250, 238), width=1)
    draw.line((2, 26, width - 3, 26), fill=(8, 15, 18), width=1)
    draw.ellipse((width - 19, height - 18, width - 4, height - 3),
                 fill=(190, 120, 85), outline=(80, 40, 20), width=1)
    return image


def run(output_dir=Path("v211-dual-model-proof"), scale=2):
    if scale not in (2, 4):
        raise ValueError("Research A/B supports scale 2 or 4")
    _basic_sr_import_compat()

    # Fail before expensive inference when the test weights are absent or
    # corrupt. Their download and checksum verification belong to the CI.
    from signprint_ai.v211_hat_engine import validate_checkpoint, checkpoint_path
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from tools.v211_generate_ab import run_pair

    validate_checkpoint(checkpoint_path())
    adapter = NiyomSilpCoreAdapter()
    if not adapter.selected_model_available("v2_hat_assist"):
        raise RuntimeError("V2 and HAT weights must both exist for real A/B")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = output_dir / "synthetic_sign_photo.png"
    synthetic_sign_photo().save(source)
    report = run_pair(
        source, output_dir, scale=scale, dpi=300,
        device="cpu", adapter=adapter,
    )
    # Model outputs must reflect actual inference, not the test stub.
    if report["processing"]["v2_model"] != "RealESRGAN_x4plus":
        raise AssertionError("V2 primary model did not run")
    if report["processing"]["assisted_model"] != "V2 RealESRGAN_x4plus + HAT Assist":
        raise AssertionError("V2 + HAT actual model pair did not run")
    if report["overall"]["pixel_count"] == 0:
        raise AssertionError("A/B produced an empty result")
    if not math.isfinite(report["overall"]["mean_abs_change"]):
        raise AssertionError("A/B produced non-finite image differences")
    if report["overall"]["changed_gt_3_pct"] == 0:
        # This is not evidence of lack of potential: only that the current
        # blending settings generated no visible change on *this* input.
        report["warning"] = "Current assisted output is indistinguishable above 3/255 on this test."
    report["checkpoint_inference_verified"] = True
    report["commercial_weights_redistribution_approved"] = False
    report["physical_print_certified"] = False
    (output_dir / "A_B_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "checkpoint_inference_verified": True,
        "models": report["processing"],
        "overall": report["overall"],
        "existing_v2_edges": report["existing_v2_edges"],
        "flat_ink_fills": report["flat_ink_fills"],
        "quality_improvement_certified": False,
        "physical_print_certified": False,
    }, indent=2))
    return report


if __name__ == "__main__":
    run()
