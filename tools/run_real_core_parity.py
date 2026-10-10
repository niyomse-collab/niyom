"""CPU-only parity gate against the unchanged legacy engine using real weights.

This test is intentionally *outside* the app's startup/worker/export path.
It does not exercise a GUI or make legal/visual quality guarantees.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"


def create_test_image(path: Path, width: int = 9, height: int = 7) -> None:
    """Tiny synthetic color/edge/texture fixture to bound CI CPU runtime."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            img.putpixel((x, y), ((x * 29 + y * 11) % 256,
                                      (x * 7 + y * 39) % 256,
                                      (x * 43 + y * 5) % 256))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 3, 2), fill=(240, 4, 16))
    draw.line((0, height - 1, width - 1, 0), fill=(20, 245, 90), width=1)
    img.save(path, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "RealESRGAN_x4plus.pth")
    parser.add_argument("--output", type=Path, default=ROOT / "core-parity-report")
    parser.add_argument("--scales", nargs="+", type=int, default=[2, 4, 8])
    args = parser.parse_args()
    model = args.model.resolve()
    if not model.is_file():
        raise FileNotFoundError(f"Missing model: {model}")
    actual_digest = hashlib.sha256(model.read_bytes()).hexdigest()
    if actual_digest != MODEL_SHA256:
        raise ValueError(f"Model SHA256 differs from known baseline: {actual_digest}")
    if not set(args.scales).issubset({2, 4, 8}):
        raise ValueError("Only 2x/4x/8x supported")

    # BasicSR 1.4.2 references torchvision.transforms.functional_tensor removed
    # in recent TorchVision. Existing packaging applies this import alias.
    # Only the test process requires this shim; existing engine/UI is unmodified.
    sys.path.insert(0, str(ROOT))
    import pyi_rth_basicsr_compat  # noqa: F401
    import torch
    import torchvision
    import basicsr
    import realesrgan
    from app.engine.realesrgan_engine import RealESRGANEngine
    from independent_core.engine import CoreConfig, IndependentCore
    from independent_core.compare import compare_png

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    baseline = RealESRGANEngine(
        model_path=model, tile=256, tile_pad=10, pre_pad=0,
        half=False, device_override="cpu"
    )
    candidate = IndependentCore(CoreConfig(
        model_path=model, device="cpu", tile=256,
        tile_pad=10, pre_pad=0, fp16=False
    ))
    report = {
        "model_sha256": actual_digest,
        "device": "cpu",
        "dtype": "FP32",
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "basicsr": getattr(basicsr, "__version__", "unknown"),
        "realesrgan": getattr(realesrgan, "__version__", "unknown"),
        "python": platform.python_version(),
        "scales": {},
        "note": "Synthetic tiny images only. Not proof of GPU parity or commercial-print quality."
    }
    passed = True
    for scale in args.scales:
        # One scale uses the same original image for both engines.
        source = out / f"fixture_{scale}x.png"
        create_test_image(source, width=5 if scale == 8 else 9, height=5 if scale == 8 else 7)
        old_png = out / f"legacy_{scale}x.png"
        new_png = out / f"niyomsil_{scale}x.png"

        # Exercise the actual legacy engine; the legacy adapter's 8x recipe
        # is its 4x enhance followed by 2x enhance on a saved PNG.
        if scale == 8:
            pass1 = out / "legacy_8x_stage4.png"
            baseline.enhance(source, pass1, scale=4)
            baseline.enhance(pass1, old_png, scale=2)
        else:
            baseline.enhance(source, old_png, scale=scale)

        candidate.enhance(source, new_png, scale=scale)
        stats = compare_png(old_png, new_png)
        report["scales"][str(scale)] = stats
        passed = passed and stats["same_pixels"]
        print(f"{scale}x: dimensions_equal={stats['same_dimensions']} pixel_equal={stats['same_pixels']}", flush=True)

    report["pass"] = passed
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
