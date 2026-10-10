"""Deterministic signage regression using real Real-ESRGAN weights on CPU.

This generates synthetic THAI sign/flat-gradient/illustrated portrait inputs.
It compares the old imported reference engine with the independent NiyomSilp
adapter on the same inputs and produces saved PNGs and structured metrics.

Important limitations:
* Fonts/fixtures are not customer artwork.
* Pixel parity with old ARM does not prove the old engine has no tile seams.
* This CPU test does not prove CUDA compatibility, fidelity of real faces,
  perceptual improvement, or export colors after ICC conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
TILE = 256


def thai_font() -> tuple[ImageFont.FreeTypeFont, str]:
    """Require an installed font with Thai coverage, no silent bitmap fallback."""
    selected = subprocess.check_output(
        ["fc-match", "-f", "%{file}", ":lang=th"], text=True
    ).strip()
    if not selected or not Path(selected).is_file():
        raise RuntimeError("Thai-supporting font unavailable; install fonts-thai-tlwg")
    return ImageFont.truetype(selected, 28), selected


def make_thai_sign(path: Path, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """264×262 crosses both native tile boundaries at x=256 and y=256."""
    width, height = 264, 262
    img = Image.new("RGB", (width, height), (242, 242, 238))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width - 1, 68), fill=(192, 12, 24))
    draw.rectangle((0, 68, width - 1, 145), fill=(247, 238, 208))
    draw.rectangle((0, 145, width - 1, height - 1), fill=(19, 23, 29))
    draw.text((8, 11), "นิยมศิลป์ดีไซน์", fill=(255, 255, 255), font=font)
    draw.text((8, 77), "งานป้ายไวนิล", fill=(31, 25, 21), font=font)
    draw.text((8, 155), "ราคา 100 บาท", fill=(255, 225, 47), font=font)
    # High-contrast fine elements cross the two tile boundaries.
    for y in range(210, height, 6):
        draw.line((230, y, 263, y), fill=(y * 7 % 255, 190, 240), width=1)
    for x in range(185, width, 13):
        draw.line((x, 214, x, height - 1), fill=(220, 120, 80), width=1)
    img.save(path, format="PNG")
    return img.size


def make_flat_gradient(path: Path) -> tuple[int, int]:
    """272×92 crosses the horizontal tile boundary, tests flat color/halos."""
    width, height = 272, 92
    x = np.linspace(0, 1, width, dtype=np.float32)
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = (24 + 210 * x).astype(np.uint8)[None, :]
    image[:, :, 1] = (230 - 155 * x).astype(np.uint8)[None, :]
    image[:, :, 2] = (100 + 90 * x).astype(np.uint8)[None, :]
    image[:, 20:64] = (14, 22, 30)
    image[24:27, 242:272] = (250, 250, 250)
    image[48:51, 250:272] = (251, 30, 30)
    Image.fromarray(image).save(path, format="PNG")
    return width, height


def make_portrait_illustration(path: Path) -> tuple[int, int]:
    """Reproducible human-like illustration, NOT a real portrait photograph."""
    width, height = 128, 144
    yy, xx = np.mgrid[0:height, 0:width]
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[..., 0] = np.clip(99 + (yy * 0.7), 0, 255)
    image[..., 1] = np.clip(135 + (xx * 0.3), 0, 255)
    image[..., 2] = np.clip(160 + yy * 0.1, 0, 255)
    img = Image.fromarray(image)
    draw = ImageDraw.Draw(img)
    draw.ellipse((24, 11, 103, 115), fill=(54, 39, 31))
    draw.ellipse((29, 30, 99, 115), fill=(205, 152, 108))
    draw.ellipse((43, 58, 51, 63), fill=(30, 19, 16))
    draw.ellipse((80, 58, 88, 63), fill=(30, 19, 16))
    draw.line((63, 63, 61, 84, 68, 86), fill=(139, 92, 71), width=2)
    draw.arc((49, 82, 80, 102), 5, 172, fill=(120, 42, 46), width=2)
    draw.polygon([(0, 143), (20, 108), (48, 117), (64, 136),
                  (87, 118), (106, 110), (127, 143)], fill=(17, 26, 60))
    img.save(path, format="PNG")
    return img.size


def compare_internal_tile_band(old_png: Path, new_png: Path,
                               source_size: tuple[int, int], scale: int) -> dict:
    """Compare differences specifically around expected tile joins.

    A zero difference here means only that old and new share the same behavior,
    NOT that an artifact-free stitch has been demonstrated.
    """
    with Image.open(old_png) as a, Image.open(new_png) as b:
        left, right = np.asarray(a.convert("RGB")), np.asarray(b.convert("RGB"))
    if left.shape != right.shape:
        return {"bands_compared": 0, "max_diff": None, "changed_pixels": None}
    bands = np.zeros(left.shape[:2], dtype=bool)
    n_x = 0
    n_y = 0
    for source_x in range(TILE, source_size[0], TILE):
        pixel_x = source_x * scale
        bands[:, max(0, pixel_x - 2):min(left.shape[1], pixel_x + 2)] = True
        n_x += 1
    for source_y in range(TILE, source_size[1], TILE):
        pixel_y = source_y * scale
        bands[max(0, pixel_y - 2):min(left.shape[0], pixel_y + 2), :] = True
        n_y += 1
    delta = np.abs(left.astype(np.int16) - right.astype(np.int16))
    band_values = delta[bands]
    return {
        "tile_boundaries_x": n_x,
        "tile_boundaries_y": n_y,
        "band_width_pixels": 4,
        "bands_compared": int(bands.sum()),
        "max_diff": int(band_values.max()) if band_values.size else None,
        "changed_pixels": int(np.count_nonzero(np.any(delta[bands] > 0, axis=-1))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "RealESRGAN_x4plus.pth")
    parser.add_argument("--output", type=Path, default=ROOT / "signage-regression")
    args = parser.parse_args()
    model = args.model.resolve()
    if not model.is_file():
        raise FileNotFoundError("Missing RealESRGAN_x4plus weights")
    # Stream so the checkpoint does not remain in RAM during large-image inference.
    digest = hashlib.file_digest(model.open("rb"), "sha256").hexdigest()
    if digest != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Model hash mismatch: {digest}")

    sys.path.insert(0, str(ROOT))
    import pyi_rth_basicsr_compat  # noqa: F401
    import torch
    from app.engine.realesrgan_engine import RealESRGANEngine
    from independent_core import CoreConfig, IndependentCore
    from independent_core.compare import compare_png

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font, font_path = thai_font()

    reference = RealESRGANEngine(
        model_path=model, tile=TILE, tile_pad=10, pre_pad=0,
        half=False, device_override="cpu"
    )
    proposed = IndependentCore(CoreConfig(
        model_path=model, device="cpu", tile=TILE,
        tile_pad=10, pre_pad=0, fp16=False
    ))

    specs = (
        ("thai_text_two_axis_tiles", make_thai_sign, 2, font),
        ("flat_gradient_x_tile", make_flat_gradient, 4, None),
        ("portrait_illustration", make_portrait_illustration, 4, None),
    )
    report = {
        "model_sha256": digest,
        "reference": "Unmodified ARM RealESRGANEngine with official RealESRGAN_x4plus.pth",
        "candidate": "Independent NiyomSilp adapter with the same official model",
        "cpu_fp32": True,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "tile": TILE,
        "tile_pad": 10,
        "font_used": Path(font_path).name,
        "cases": {},
        "limitations": [
            "These are generated test inputs, not real customer images.",
            "An illustration is not a photograph/real face restoration test.",
            "Parity compares to ARM, it cannot prove absence of ARM tile seams.",
            "No CUDA GPU, print-size, export ICC, or end-to-end GUI tests."
        ],
    }
    passed = True
    for name, creator, scale, maybe_font in specs:
        source = output / f"{name}_source.png"
        if maybe_font is None:
            size = creator(source)
        else:
            size = creator(source, maybe_font)
        before = output / f"{name}_arm_{scale}x.png"
        after = output / f"{name}_niyomsil_{scale}x.png"
        print(f"Processing {name}, source={size}, scale={scale}...", flush=True)
        reference.enhance(source, before, scale=scale)
        proposed.enhance(source, after, scale=scale)
        metrics = compare_png(before, after)
        metrics["tile_count"] = math.ceil(size[0] / TILE) * math.ceil(size[1] / TILE)
        metrics["source_dimensions"] = list(size)
        metrics["scale"] = scale
        metrics["tile_boundary_difference"] = compare_internal_tile_band(before, after, size, scale)
        report["cases"][name] = metrics
        print(f"{name}: same_pixels={metrics['same_pixels']}, "
              f"changed_pixels={metrics.get('changed_pixels')}, "
              f"tile_count={metrics['tile_count']}", flush=True)
        passed &= metrics["same_pixels"]

    report["pass"] = bool(passed)
    (output / "signage_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
