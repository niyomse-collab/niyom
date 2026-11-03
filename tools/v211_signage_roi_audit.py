"""Private signage regions: prepare source crops and compare actual V2/V2.1.1 outputs.

Does not run AI models, upload customer files, or certify image improvement.
Usage:
  python -m tools.v211_signage_roi_audit --source photo.png --regions regions.json --out private/qa
  python -m tools.v211_signage_roi_audit --source photo.png --v2 v2.png --super v211.png --regions regions.json --out private/qa
Regions JSON: {"regions":[{"id":"heading","kind":"styled_fx_text","box":[0.1,0.1,0.9,0.4]}]}
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from tools.v211_ab_report import _check_qa_size, compare_images

KINDS = frozenset({
    "plain_small_text", "styled_fx_text", "thai_ornament", "gold_metal",
    "transparent_edge", "soft_gradient", "face", "product", "other",
    # Image-only restoration covers scripts beyond Thai; never retypes them.
    "microtext", "latin_text", "chinese_text", "multiscript_text",
    # Natural material must remain natural, not smooth plastic.
    "foliage", "fabric", "natural_texture", "skin", "food_texture",
})
NATURAL_TEXTURE_KINDS = frozenset({
    "foliage", "fabric", "natural_texture", "skin", "food_texture", "face", "product"
})

def load_regions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    regions = data.get("regions") if isinstance(data, dict) else data
    if not isinstance(regions, list) or not regions:
        raise ValueError("Regions JSON requires a nonempty regions list")
    names, valid = set(), []
    for item in regions:
        if not isinstance(item, dict):
            raise ValueError("Each region must be an object")
        name, kind, box = item.get("id"), item.get("kind"), item.get("box")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
            raise ValueError("Region id must be safe ASCII characters")
        if name in names:
            raise ValueError("Duplicate region id")
        if kind not in KINDS:
            raise ValueError(f"Invalid signage region kind: {kind}")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("Region box must contain four normalized numbers")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in box):
            raise ValueError("Region coordinates must be finite numbers")
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Region box must be within normalized [0,1]")
        names.add(name)
        valid.append({"id": name, "kind": kind, "box": box})
    return valid

def _box(box, size):
    w, h = size
    x1, y1, x2, y2 = box
    a, b = int(x1 * w), int(y1 * h)
    return (a, b, max(int(math.ceil(x2 * w)), a + 1),
            max(int(math.ceil(y2 * h)), b + 1))

def _matte(image, rgb):
    rgba = image.convert("RGBA")
    bg = Image.new("RGBA", image.size, rgb + (255,))
    return Image.alpha_composite(bg, rgba).convert("RGB")

def _preview(source, baseline, candidate, rgb):
    if baseline is None:
        return _matte(source, rgb)
    # Resizing the source is only for the visual panel, never for metrics.
    size = baseline.size
    imgs = (source.resize(size, Image.Resampling.LANCZOS), baseline, candidate)
    gap, header = 12, 28
    canvas = Image.new("RGB", (size[0] * 3 + gap * 2, size[1] + header), (35, 35, 35))
    painter = ImageDraw.Draw(canvas)
    for i, (im, title) in enumerate(zip(imgs, (
        "Source (display only)", "Approved V2", "Experimental V2.1.1"))):
        left = i * (size[0] + gap)
        canvas.paste(_matte(im, rgb), (left, header))
        painter.text((left + 4, 7), title, fill="white")
    return canvas

def _delta(before, after):
    a = np.asarray(before.convert("RGBA"))
    b = np.asarray(after.convert("RGBA"))
    mask = a[:, :, 3] > 0
    if not mask.any():
        return {"visible_pixels": 0, "mean_abs_rgb_change": None,
                "p95_max_channel_change": None, "changed_gt3_pct": None}
    diff = np.abs(a[:, :, :3].astype(np.int16) - b[:, :, :3].astype(np.int16))
    maximum = diff.max(axis=2)[mask]
    return {
        "visible_pixels": int(mask.sum()),
        "mean_abs_rgb_change": round(float(diff[mask].mean()), 4),
        "p95_max_channel_change": round(float(np.percentile(maximum, 95)), 4),
        "changed_gt3_pct": round(float((maximum > 3).mean() * 100), 4),
    }

def _texture_diagnostic(reference, candidate):
    """High-frequency texture change versus approved V2, not a quality score.

    Raster sharpening can increase energy by adding fake leaf veins, while
    denoising can suppress real leaf/fabric/skin texture. Both require visual
    review. We do not infer an object's identity or invent missing pixels.
    """
    import cv2
    a = np.asarray(reference.convert("RGBA"), dtype=np.uint8)
    b = np.asarray(candidate.convert("RGBA"), dtype=np.uint8)
    mask = (a[:, :, 3] > 32) & (b[:, :, 3] > 32)
    if min(a.shape[:2]) < 16 or np.count_nonzero(mask) < 128:
        return {"diagnostic_available": False, "reason": "too_few_visible_pixels",
                "quality_certified": False}

    def high_frequency_energy(rgba):
        rgb = rgba[..., :3].astype(np.float32)
        detail = rgb - cv2.GaussianBlur(rgb, (0, 0), 1.2)
        return float(np.mean(np.abs(detail[mask])))

    before = high_frequency_energy(a)
    after = high_frequency_energy(b)
    ratio = after / before if before >= 1.0 else None
    return {
        "diagnostic_available": ratio is not None,
        "v2_high_frequency_energy": round(before, 5),
        "v211_high_frequency_energy": round(after, 5),
        "relative_detail_energy": round(ratio, 5) if ratio is not None else None,
        "possible_texture_loss_review": bool(ratio is not None and ratio < .65),
        "possible_artificial_crunch_review": bool(ratio is not None and ratio > 1.65),
        "quality_certified": False,
        "note": "Energy alone cannot identify real leaf veins, skin details or invented texture.",
    }


def _write_regions(original, baseline, candidate, regions, out, report):
    out.mkdir(parents=True, exist_ok=True)
    for item in regions:
        name, kind, norm = item["id"], item["kind"], item["box"]
        original_crop = original.crop(_box(norm, original.size))
        a = b = None
        entry = {**item, "source_crop_pixels": list(original_crop.size)}
        if baseline is not None:
            a = baseline.crop(_box(norm, baseline.size))
            b = candidate.crop(_box(norm, candidate.size))
            entry["paired_crop_pixels"] = list(a.size)
            entry["v2_to_v211_change"] = _delta(a, b)
            if kind in NATURAL_TEXTURE_KINDS:
                entry["material_texture_diagnostic"] = _texture_diagnostic(a, b)
                diagnostic = entry["material_texture_diagnostic"]
                if (diagnostic.get("possible_texture_loss_review")
                        or diagnostic.get("possible_artificial_crunch_review")):
                    report["material_review_required"].append(name)
        mattes = {"gray": (90, 90, 90)}
        if kind == "transparent_edge" or "A" in original.getbands():
            mattes.update({"white": (255, 255, 255),
                           "black": (0, 0, 0), "red": (220, 30, 30)})
        entry["previews"] = []
        for label, color in mattes.items():
            filepath = out / f"{name}_{label}.png"
            _preview(original_crop, a, b, color).save(filepath)
            entry["previews"].append(filepath.name)
        report["regions"].append(entry)

def run_audit(source, regions_file, output_dir, *, v2=None, super_path=None):
    if (v2 is None) != (super_path is None):
        raise ValueError("Provide both --v2 and --super, or neither")
    source, output_dir = Path(source), Path(output_dir)
    if not source.is_file():
        raise FileNotFoundError(source)
    regions = load_regions(regions_file)
    paired = v2 is not None
    report = {
        "source_filename": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "ab_comparison_available": paired,
        "quality_improvement_certified": False,
        "print_certified": False, "face_identity_certified": False,
        "material_review_required": [],
        "note": "Pixel differences do not prove better quality. Human A/B and print review required.",
        "regions": [],
    }
    with Image.open(source) as original:
        original.load()
        _check_qa_size(original.size)
        report["source_pixels"] = list(original.size)
        report["source_has_alpha"] = (
            "A" in original.getbands() or "transparency" in original.info
        )
        if paired:
            # This existing function rejects different pixels, alpha, ICC and DPI.
            report["full_image_deltas"] = compare_images(v2, super_path)
            with Image.open(v2) as baseline, Image.open(super_path) as candidate:
                baseline.load()
                candidate.load()
                if abs(original.width / original.height -
                       baseline.width / baseline.height) > 0.005:
                    raise ValueError("Source and output aspect ratios do not match")
                _write_regions(original, baseline, candidate, regions, output_dir, report)
        else:
            _write_regions(original, None, None, regions, output_dir, report)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "SIGNAGE_ROI_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--regions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--v2", type=Path)
    parser.add_argument("--super", type=Path)
    args = parser.parse_args(argv)
    result = run_audit(args.source, args.regions, args.out,
                       v2=args.v2, super_path=args.super)
    print(json.dumps({"ab_comparison_available": result["ab_comparison_available"],
                      "regions": len(result["regions"]),
                      "quality_improvement_certified": False}, ensure_ascii=False))

if __name__ == "__main__":
    main()
