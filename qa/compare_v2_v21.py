#!/usr/bin/env python3
"""Compare aligned V2 and V2.1 printed lettering crops; NEVER certify a print.

Select one uniform interior-fill ROI and one edge ROI at identical pixel
coordinates; very large rasters require pyvips for bounded read-only crops.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

MAX_FULL_IMAGE_PIXELS = 16_000_000


def parse_roi(value):
    try:
        values = tuple(int(x) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use x,y,width,height integers") from exc
    if len(values) != 4 or min(values[:2]) < 0 or min(values[2:]) < 8:
        raise argparse.ArgumentTypeError("ROI requires x,y>=0; width,height>=8")
    return values


def read_roi(path, roi):
    x, y, w, h = roi
    with Image.open(path) as img:
        size, mode = img.size, img.mode
        blob = img.info.get("icc_profile")
        metadata = {
            "size": list(size), "mode": mode,
            "icc_sha256": hashlib.sha256(blob).hexdigest() if blob else None,
        }
        if x + w > size[0] or y + h > size[1]:
            raise ValueError("ROI exceeds output image bounds")
        if size[0] * size[1] <= MAX_FULL_IMAGE_PIXELS:
            pixels = np.asarray(img.crop((x, y, x+w, y+h))).copy()
        else:
            try:
                import pyvips
            except (ImportError, OSError) as exc:
                raise RuntimeError(
                    "NOT_TESTED: large output needs pyvips for bounded crops"
                ) from exc
            image = pyvips.Image.new_from_file(
                str(path), access="random", fail_on="error"
            )
            if image.format != "uchar" or image.bands not in (3, 4):
                raise RuntimeError("NOT_TESTED: expected 8-bit RGB/RGBA/CMYK")
            if (image.width, image.height) != size:
                raise RuntimeError("NOT_TESTED: output orientation mismatch")
            tile = image.crop(x, y, w, h)
            pixels = np.frombuffer(
                tile.write_to_memory(), np.uint8
            ).reshape(h, w, tile.bands).copy()
    return pixels, metadata


def rgb_view(pixels, mode):
    if mode == "CMYK":
        # PIL's conversion is for grain/edge diagnostics only, NOT proof
        # of ICC colour fidelity. Embedded ICC digests must match.
        return np.asarray(Image.fromarray(pixels, mode="CMYK").convert("RGB"))
    if mode == "RGBA":
        alpha = pixels[:, :, 3:4].astype(np.float32) / 255.0
        return np.rint(
            pixels[:, :, :3].astype(np.float32) * alpha + 255.0*(1-alpha)
        ).astype(np.uint8)
    if mode == "RGB":
        return pixels
    raise RuntimeError(f"NOT_TESTED: unsupported mode {mode}")


def flat_grain(pixels, mode):
    rgb = rgb_view(pixels, mode)
    median = np.asarray(
        Image.fromarray(rgb).filter(ImageFilter.MedianFilter(3))
    )
    residual = np.abs(rgb.astype(np.int16)-median.astype(np.int16))
    return round(float(residual[2:-2, 2:-2].mean()), 3)


def edge_strength(pixels, mode):
    rgb = rgb_view(pixels, mode).astype(np.float32)
    gray = rgb[..., 0]*.299 + rgb[..., 1]*.587 + rgb[..., 2]*.114
    dx = abs(np.diff(gray, axis=1))[:, 2:-2]
    dy = abs(np.diff(gray, axis=0))[2:-2, :]
    return round(float(np.percentile(
        np.concatenate((dx.ravel(), dy.ravel())), 99
    )), 3)


def compare(baseline, candidate, flat_roi, edge_roi):
    result = {
        "comparison": "V2 versus V2.1",
        "baseline": str(baseline), "candidate": str(candidate),
        "flat_roi": list(flat_roi), "edge_roi": list(edge_roi),
        "automated_check": "NOT_TESTED",
        "print_certification": "NOT_CERTIFIED", "warnings": [],
    }
    try:
        measurements = {}
        for name, roi in (("flat", flat_roi), ("edge", edge_roi)):
            old, oldmeta = read_roi(baseline, roi)
            new, newmeta = read_roi(candidate, roi)
            if oldmeta != newmeta or old.shape != new.shape:
                raise RuntimeError(
                    "NOT_TESTED: output size, colour mode or ICC differs"
                )
            if oldmeta["mode"] == "RGBA" and not np.array_equal(
                old[..., 3], new[..., 3]
            ):
                result["warnings"].append(f"{name} ROI alpha plane changed")
            metric = flat_grain if name == "flat" else edge_strength
            measurements[name] = {
                "v2": metric(old, oldmeta["mode"]),
                "v21": metric(new, oldmeta["mode"]),
            }
            result["metadata"] = oldmeta
        result["measurements"] = measurements
        start, end = measurements["flat"]["v2"], measurements["flat"]["v21"]
        if start > 0.3 and end > start*1.15:
            result["warnings"].append(
                "Flat-colour noise increased by >15% in chosen text-fill ROI"
            )
        before, after = measurements["edge"]["v2"], measurements["edge"]["v21"]
        if before > 5 and after < before*.8:
            result["warnings"].append("High-contrast edge strength decreased by >20%")
        if before > 5 and after > before*1.5:
            result["warnings"].append(
                "Edge response rose by >50%; inspect oversharpening or halos"
            )
        result["automated_check"] = (
            "POSSIBLE_REGRESSION" if result["warnings"]
            else "NO_AUTOMATED_REGRESSION_DETECTED"
        )
        result["reason"] = (
            "Two-crop metrics are screening only; Photoshop and actual printing"
            " are required for sign-off"
        )
    except Exception as exc:
        result["automated_check"] = "NOT_TESTED"
        result["reason"] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--flat-roi", type=parse_roi, required=True)
    parser.add_argument("--edge-roi", type=parse_roi, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare(args.baseline, args.candidate, args.flat_roi, args.edge_roi)
    report["checked_utc"] = datetime.now(timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f'{report["automated_check"]}: {report.get("reason", "")}')
    return {
        "NO_AUTOMATED_REGRESSION_DETECTED": 0,
        "POSSIBLE_REGRESSION": 1,
        "NOT_TESTED": 2,
    }[report["automated_check"]]


if __name__ == "__main__":
    raise SystemExit(main())
