"""Local NVIDIA real-image parity gate. Does NOT modify the installed app.

Use with the SAME official model file and a source photo approved by its owner.
Reports CUDA model/VRAM and pixel differences. There is no CPU fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ARM and NiyomSilp neural output on NVIDIA CUDA")
    parser.add_argument("--source", required=True, type=Path, help="Shop-owned RGB image; remains unchanged")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "RealESRGAN_x4plus.pth")
    parser.add_argument("--out", type=Path, default=ROOT / "local-qa-results" / "gpu")
    parser.add_argument("--scale", type=int, choices=(2, 4), default=2)
    args = parser.parse_args()
    if not args.source.is_file() or not args.model.is_file():
        print("Missing local input image or exact official model file.", file=sys.stderr)
        return 3
    if checksum(args.model) != MODEL_SHA256:
        print("Model SHA-256 mismatch. Refusing to compare different model weights.", file=sys.stderr)
        return 4
    if args.source.resolve() == args.out.resolve():
        print("Output cannot overwrite input.", file=sys.stderr)
        return 5

    import torch
    if not torch.cuda.is_available() or torch.version.cuda is None:
        print("No NVIDIA CUDA device. GPU validation NOT passed.", file=sys.stderr)
        return 2

    # Import shim needed by BasicSR with recent TorchVision; scope is this test only.
    import pyi_rth_basicsr_compat  # noqa: F401
    from app.engine.realesrgan_engine import RealESRGANEngine
    from independent_core import CoreConfig, IndependentCore
    from independent_core.compare import compare_png
    from PIL import Image

    with Image.open(args.source) as sample:
        input_dimensions = sample.size
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    baseline_path = out / "arm-reference.png"
    candidate_path = out / "niyomsil-candidate.png"
    start = time.perf_counter()

    # Construct/run the two models sequentially to avoid unnecessary VRAM sharing.
    reference = RealESRGANEngine(
        model_path=args.model, tile=256, tile_pad=10, pre_pad=0,
        half=False, device_override="cuda"
    )
    torch.cuda.reset_peak_memory_stats()
    reference.enhance(args.source, baseline_path, scale=args.scale)
    torch.cuda.synchronize()
    reference_seconds = time.perf_counter() - start
    reference_vram_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
    del reference
    import gc
    gc.collect()
    torch.cuda.empty_cache()

    started_candidate = time.perf_counter()
    candidate = IndependentCore(CoreConfig(
        model_path=args.model, device="cuda", tile=256, tile_pad=10,
        pre_pad=0, fp16=False
    ))
    torch.cuda.reset_peak_memory_stats()
    candidate.enhance(args.source, candidate_path, scale=args.scale)
    torch.cuda.synchronize()
    candidate_seconds = time.perf_counter() - started_candidate
    candidate_vram_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
    del candidate
    gc.collect()
    torch.cuda.empty_cache()

    comparison = compare_png(baseline_path, candidate_path)
    results = {
        "passed": comparison["same_pixels"],
        "source_dimensions": list(input_dimensions),
        "model_sha256": MODEL_SHA256,
        "gpu_name": torch.cuda.get_device_name(0),
        "pytorch_version": str(torch.__version__),
        "cuda_runtime": torch.version.cuda,
        "scale": args.scale,
        "precision": "FP32",
        "reference_seconds": round(reference_seconds, 2),
        "candidate_seconds": round(candidate_seconds, 2),
        "reference_peak_vram_mb": round(reference_vram_mb, 1),
        "candidate_peak_vram_mb": round(candidate_vram_mb, 1),
        "pixel_comparison": comparison,
        "note": "One-image parity is not proof of absence of seams or print quality."
    }
    (out / "gpu_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
