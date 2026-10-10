"""Explicit real-NVIDIA CUDA parity check; this script must NEVER silently skip.

Runs on a developer-owned NVIDIA/CUDA computer using an approved input photo.
Does not patch or switch the installed Windows application.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path, help="Locally owned test image")
    p.add_argument("--model", type=Path, default=ROOT/"models"/"RealESRGAN_x4plus.pth")
    p.add_argument("--out", type=Path, default=ROOT/"gpu-parity-evidence")
    p.add_argument("--scale", type=int, default=2, choices=(2, 4))
    args = p.parse_args()
    import pyi_rth_basicsr_compat  # noqa: F401
    import torch
    if not torch.cuda.is_available():
        print("CUDA unavailable: GPU parity NOT verified", file=sys.stderr)
        return 2
    if not args.source.is_file() or not args.model.is_file():
        print("Input photo or model missing", file=sys.stderr)
        return 3
    with args.model.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != MODEL_SHA256:
        print("Model SHA mismatch: do not continue", file=sys.stderr)
        return 4

    from app.engine.realesrgan_engine import RealESRGANEngine
    from independent_core import CoreConfig, IndependentCore
    from independent_core.compare import compare_png
    args.out.mkdir(parents=True, exist_ok=True)
    old, new = args.out/"arm.png", args.out/"niyomsil.png"
    legacy = RealESRGANEngine(model_path=args.model, tile=256, tile_pad=10,
                              pre_pad=0, half=False, device_override="cuda")
    modern = IndependentCore(CoreConfig(
        model_path=args.model, device="cuda", tile=256, tile_pad=10, pre_pad=0, fp16=False))
    legacy.enhance(args.source, old, scale=args.scale)
    modern.enhance(args.source, new, scale=args.scale)
    report = {
        "model": digest, "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "scale": args.scale, "source": str(args.source),
        "comparison": compare_png(old, new),
        "note": "Parity on one NVIDIA image is not acceptance of print color/GUI quality."
    }
    (args.out/"gpu_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["comparison"]["same_pixels"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
