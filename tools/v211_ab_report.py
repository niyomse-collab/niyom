"""Compare identical-size V2 and V2.1.1 outputs without declaring quality.

Usage:
  python -m tools.v211_ab_report --v2 V2.png --super Super.png --out local-qa

Runs entirely locally; never uploads customer photos. The output is
diagnostic evidence for an independent human review, not a pass certificate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

# Diagnostic arrays are per-pixel float/int tensors. Large vinyl masters
# must be compared on representative crops, not forced into RAM at once.
MAX_QA_PIXELS = 16_000_000


def _check_qa_size(size):
    if size[0] * size[1] > MAX_QA_PIXELS:
        raise ValueError(
            "A/B diagnostic exceeds 16 megapixels. Export the same "
            "representative crop from V2 and V2.1.1 at identical pixels "
            "before running this local quality check."
        )


def _rgb_and_alpha(image: Image.Image):
    rgba = np.asarray(image.convert("RGBA"))
    if "A" in image.getbands() or "transparency" in image.info:
        alpha = rgba[:, :, 3].copy()
    else:
        alpha = np.full(rgba.shape[:2], 255, dtype=np.uint8)
    return rgba[:, :, :3].copy(), alpha


def _metadata(image: Image.Image):
    dpi = image.info.get("dpi")
    return {
        "dpi": [round(float(d), 3) for d in dpi] if dpi else None,
        "icc_profile_present": bool(image.info.get("icc_profile")),
        "icc_profile_bytes": len(image.info.get("icc_profile") or b""),
        "mode": image.mode,
        "pixels": list(image.size),
    }


def _regions_to_mask(regions, width, height):
    mask = np.zeros((height, width), dtype=bool)
    for coords in regions or ():
        if len(coords) != 4 or not all(np.isfinite(v) for v in coords):
            raise ValueError("face regions must be finite normalized rectangles")
        x1, y1, x2, y2 = map(float, coords)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("face coordinates must be within normalized [0,1]")
        left, top = int(np.floor(x1 * width)), int(np.floor(y1 * height))
        right, bottom = int(np.ceil(x2 * width)), int(np.ceil(y2 * height))
        mask[top:bottom, left:right] = True
    return mask


def compare_images(v2_path, super_path, *, face_regions=()):
    """Return objective deltas; never claim aesthetic or identity improvement."""
    with Image.open(v2_path) as v2_image, Image.open(super_path) as super_image:
        if v2_image.size != super_image.size:
            raise ValueError("Comparison invalid: different output pixel dimensions")
        _check_qa_size(v2_image.size)
        meta_v2, meta_super = _metadata(v2_image), _metadata(super_image)
        if v2_image.info.get("icc_profile") != super_image.info.get("icc_profile"):
            raise ValueError("Comparison invalid: ICC profiles differ")
        dpi0, dpi1 = v2_image.info.get("dpi"), super_image.info.get("dpi")
        if (dpi0 is None) != (dpi1 is None):
            raise ValueError("Comparison invalid: DPI metadata differs")
        if dpi0 and dpi1 and any(abs(float(a) - float(b)) > 1 for a, b in zip(dpi0, dpi1)):
            raise ValueError("Comparison invalid: DPI differs by >1")
        base, alpha_v2 = _rgb_and_alpha(v2_image)
        enhanced, alpha_super = _rgb_and_alpha(super_image)
    if not np.array_equal(alpha_v2, alpha_super):
        raise ValueError("Comparison invalid: output alpha planes differ")

    height, width = base.shape[:2]
    visible = alpha_v2 > 0
    if not visible.any():
        raise ValueError("Comparison invalid: entirely transparent output")
    face = _regions_to_mask(face_regions, width, height) & visible
    delta = np.abs(base.astype(np.int16) - enhanced.astype(np.int16))
    maximum = delta.max(axis=2)
    gray = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
    edge_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    edge_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(edge_x, edge_y) > 45
    edge &= visible
    # Flat print fills are identified from V2, not from the new result.
    flat = (cv2.magnitude(edge_x, edge_y) < 7) & visible & ~face

    def measure(mask):
        if not mask.any():
            return {"pixel_count": 0, "mean_abs_change": None, "changed_gt_3_pct": None}
        values = delta[mask].astype(np.float64)
        return {
            "pixel_count": int(mask.sum()),
            "mean_abs_change": round(float(values.mean()), 5),
            "changed_gt_3_pct": round(float((maximum[mask] > 3).mean() * 100), 4),
        }
    return {
        "v2_metadata": meta_v2,
        "super_metadata": meta_super,
        "same_pixels": True,
        "same_alpha": True,
        "same_icc": True,
        "overall": measure(visible),
        "existing_v2_edges": measure(edge),
        "flat_ink_fills": measure(flat),
        "selected_face_regions": measure(face),
        "max_absolute_channel_difference": int(maximum[visible].max()),
        "mean_rgb_channel_shift": [
            round(float(v), 5) for v in
            (enhanced.astype(np.float32) - base.astype(np.float32))[visible].mean(axis=0)
        ],
        "quality_improvement_certified": False,
        "face_identity_certified": False,
        "print_certified": False,
        "note": "Pixel differences are not evidence of better restoration. Review equal-size visual crops and real print.",
    }


def render_comparison(v2_path, super_path, output_path):
    with Image.open(v2_path) as first, Image.open(super_path) as second:
        if first.size != second.size:
            raise ValueError("Cannot render unequal-sized comparison images")
        _check_qa_size(first.size)
        # Flat grey matte makes transparent PNGs comparable without revealing
        # arbitrary hidden RGB values and without changing their source files.
        def matte(image):
            rgba = image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (50, 50, 50, 255))
            return Image.alpha_composite(bg, rgba).convert("RGB")
        left, right = matte(first), matte(second)
    gap, header = 24, 35
    result = Image.new("RGB", (left.width * 2 + gap, left.height + header), (30, 30, 30))
    result.paste(left, (0, header))
    result.paste(right, (left.width + gap, header))
    draw = ImageDraw.Draw(result)
    draw.text((8, 9), "V2 baseline", fill="white")
    draw.text((left.width + gap + 8, 9), "V2 + Super AI", fill="white")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--super", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--faces", type=Path, help="JSON list of normalized face rectangles")
    args = parser.parse_args(argv)
    faces = json.loads(args.faces.read_text(encoding="utf-8")) if args.faces else ()
    result = compare_images(args.v2, args.super, face_regions=faces)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "quality_deltas.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_comparison(args.v2, args.super, args.out / "v2_vs_super_ai.png")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
