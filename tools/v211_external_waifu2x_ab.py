"""Local-only V2 versus independently installed Waifu2x-ncnn comparison.

RESEARCH ONLY. Never downloads/bundles an executable, checkpoint or customer
image. Do not replace V2, launch on production images, or issue a release.
Usage:
 python -m tools.v211_external_waifu2x_ab --input crop.png \
   --exe C:/approved/waifu2x-ncnn-vulkan.exe \
   --models C:/approved/models-upconv_7_photo --out C:/private-ab --scale 2

Only untagged opaque 8-bit RGB PNG crops are supported for this research tool.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess

from PIL import Image

MAX_DIAGNOSTIC_PIXELS = 16_000_000


def build_command(exe: Path, source: Path, destination: Path, model_dir: Path,
                  *, scale: int, noise: int):
    """Return fixed argv: no shell invocation or automatic model downloads."""
    if scale not in (2, 4):
        raise ValueError("Only native 2x or 4x comparisons are supported")
    if noise not in (-1, 0, 1, 2, 3):
        raise ValueError("Invalid Waifu2x denoise setting")
    exe, source, destination, model_dir = map(Path, (exe, source, destination, model_dir))
    if not exe.is_file():
        raise FileNotFoundError(f"External executable not found: {exe}")
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Reviewed local model directory not found: {model_dir}")
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.resolve() == destination.resolve():
        raise ValueError("Cannot overwrite the original source image")
    return [str(exe.resolve()), "-i", str(source.resolve()),
            "-o", str(destination.resolve()), "-s", str(scale),
            "-n", str(noise), "-m", str(model_dir.resolve())]


def validate_source(source: Path, scale: int) -> tuple[int, int]:
    source = Path(source)
    if scale not in (2, 4):
        raise ValueError("Only native 2x or 4x comparisons are supported")
    with Image.open(source) as image:
        if image.format != "PNG" or image.mode != "RGB":
            raise ValueError("Research runner requires opaque 8-bit RGB PNG; do not flatten RGBA")
        if image.info.get("icc_profile"):
            raise ValueError("ICC-managed images must use a future color-managed path")
        if image.info.get("transparency") is not None:
            raise ValueError("Transparency cannot be silently removed")
        if image.info.get("exif"):
            raise ValueError("EXIF-bearing sources require controlled orientation handling")
        width, height = image.size
    if not width or not height or width * height * scale * scale > MAX_DIAGNOSTIC_PIXELS:
        raise ValueError("Compare a <=16MP output crop, not the full vinyl master")
    return width, height


def run_pair(source: Path, destination: Path, *, exe: Path, model_dir: Path,
             scale: int = 2, noise: int = 0, dpi: int = 300,
             adapter=None, command_runner=None):
    """Create same-pixel V2 and Waifu2x outputs plus non-certifying local QA."""
    source, destination, exe, model_dir = map(Path, (source, destination, exe, model_dir))
    width, height = validate_source(source, scale)
    if not 1 <= dpi <= 1200:
        raise ValueError("DPI out of range")
    command = build_command(exe, source, destination / "Waifu2x_ncnn_raw.png",
                            model_dir, scale=scale, noise=noise)
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.v21_graphics_ai import V21Settings
    from tools.v211_ab_report import compare_images, render_comparison

    engine = adapter if adapter is not None else NiyomSilpCoreAdapter()
    if not engine.selected_model_available("real_esrgan"):
        raise RuntimeError("Cannot compare without verified V2 Real-ESRGAN")
    destination.mkdir(parents=True, exist_ok=True)
    reference = destination / "V2_reference.png"
    raw = destination / "Waifu2x_ncnn_raw.png"
    candidate = destination / "Waifu2x_ncnn_candidate.png"
    settings = V21Settings(
        ai_scale=scale, device="AUTO", dpi=dpi,
        face_protection=False, v1_baseline=True,
        v21_v2_quality_baseline=True, v21_precision_ink=False,
        graphic_ai=False, export_format="PNG", color_mode="RGB",
    )
    result = engine.process(source, reference,
                            replace(settings, v211_photo_model="real_esrgan"), use_ai=True)
    runner = command_runner if command_runner is not None else subprocess.run
    runner(command, cwd=str(exe.resolve().parent), check=True,
           timeout=600, capture_output=True, text=True)
    if not raw.is_file():
        raise RuntimeError("Waifu2x did not produce the expected PNG")
    with Image.open(reference) as v2, Image.open(raw) as other:
        if v2.size != (width * scale, height * scale) or other.size != v2.size:
            raise ValueError("A/B invalid: candidate or V2 output has wrong dimensions")
        if other.mode not in ("RGB", "RGBA"):
            raise ValueError("A/B invalid: unexpected candidate pixel format")
        if other.mode == "RGBA" and other.getchannel("A").getextrema() != (255, 255):
            raise ValueError("A/B invalid: candidate introduced non-opaque pixels")
        if v2.info.get("icc_profile") or other.info.get("icc_profile"):
            raise ValueError("ICC metadata differ or require actual color-space conversion")
        aligned = other.convert("RGB")
        reference_dpi = v2.info.get("dpi", (dpi, dpi))
        aligned.save(candidate, format="PNG", dpi=reference_dpi)
    report = compare_images(reference, candidate)
    report["processing"] = {
        "source": str(source), "v2_model": result.get("model"),
        "candidate": "waifu2x-ncnn-vulkan", "scale": scale,
        "noise": noise, "dpi": dpi, "research_only": True,
        "candidate_not_packaged": True,
        "model_weight_redistribution_verified": False,
        "source_images_uploaded": False,
    }
    (destination / "A_B_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    render_comparison(reference, candidate, destination / "V2_vs_Waifu2x.png")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--scale", choices=(2, 4), default=2, type=int)
    parser.add_argument("--noise", choices=(-1, 0, 1, 2, 3), default=0, type=int)
    parser.add_argument("--dpi", default=300, type=int)
    args = parser.parse_args(argv)
    report = run_pair(args.input, args.out, exe=args.exe, model_dir=args.models,
                      scale=args.scale, noise=args.noise, dpi=args.dpi)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
