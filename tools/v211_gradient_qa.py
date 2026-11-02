"""Opt-in gradient banding A/B diagnostic for explicitly selected smooth ROIs.

Intentional brush grain, glossy highlights, and posterized effects are excluded.
This reports review signals only, never certifies quality improvement.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

MAX_PIXELS = 16_000_000


def compare_gradient_roi(v2_path, candidate_path, roi, axis="x"):
    """Compare adjacent RGB jumps in a user-approved opaque gradient ROI.

    ROI is (left, top, right, bottom) at equal final-output pixel resolution.
    Inputs are read-only; the function does not alter source or output files.
    """
    if axis not in ("x", "y"):
        raise ValueError("axis must be x or y")
    with Image.open(v2_path) as original, Image.open(candidate_path) as candidate:
        if original.size != candidate.size:
            raise ValueError("A/B dimensions differ")
        width, height = original.size
        if width * height > MAX_PIXELS:
            raise ValueError("Use representative crops of at most 16 megapixels")
        if len(roi) != 4 or any(type(v) is not int for v in roi):
            raise ValueError("ROI must contain four integer coordinates")
        x0, y0, x1, y1 = roi
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError("ROI is outside the image")
        if (x1-x0 if axis == "x" else y1-y0) < 3:
            raise ValueError("Gradient axis requires at least three pixels")
        a = np.asarray(original.crop(roi).convert("RGBA"), dtype=np.uint8)
        b = np.asarray(candidate.crop(roi).convert("RGBA"), dtype=np.uint8)
    if not (np.all(a[..., 3] == 255) and np.all(b[..., 3] == 255)):
        raise ValueError("Gradient ROI must be fully opaque in both images")

    def metrics(pixels):
        rgb = pixels[..., :3].astype(np.int16)
        delta = np.diff(rgb, axis=1 if axis == "x" else 0)
        magnitude = np.max(np.abs(delta), axis=2)
        return {
            "adjacent_jump_gt_8_pct": round(float(np.mean(magnitude > 8) * 100), 4),
            "adjacent_jump_gt_16_pct": round(float(np.mean(magnitude > 16) * 100), 4),
            "max_adjacent_jump": int(magnitude.max()),
        }

    v2, new = metrics(a), metrics(b)
    return {
        "roi": list(roi), "axis": axis, "v2": v2, "candidate": new,
        "new_large_jumps_review_required": new["adjacent_jump_gt_16_pct"] > v2["adjacent_jump_gt_16_pct"],
        "quality_improvement_certified": False,
        "note": "Inspect approved smooth gradients at equal pixels; exclude intentional effects and texture.",
    }
