"""Offline alpha-edge A/B diagnostic when V2 and candidate alpha differ.

This is intentionally separate from the strict same-alpha colour report.
Metrics are review signals, never automatic evidence of improvement.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

MAX_PIXELS = 16_000_000
MATTES = ((0, 0, 0), (255, 255, 255), (128, 128, 128), (255, 0, 255))


def compare_alpha_mattes(v2_path, candidate_path):
    with Image.open(v2_path) as a, Image.open(candidate_path) as b:
        if a.size != b.size:
            raise ValueError("A/B dimensions differ")
        if a.width * a.height > MAX_PIXELS:
            raise ValueError("Use representative crops of at most 16 megapixels")
        if "A" not in a.getbands() or "A" not in b.getbands():
            raise ValueError("Both inputs must have an explicit alpha channel")
        aa = np.asarray(a.convert("RGBA"), dtype=np.float32)
        bb = np.asarray(b.convert("RGBA"), dtype=np.float32)
    av, bv = aa[..., 3] / 255.0, bb[..., 3] / 255.0
    support = (av > 0) | (bv > 0)
    if not support.any():
        raise ValueError("No visible content to compare")
    edge = ((av > 0) & (av < 1)) | ((bv > 0) & (bv < 1)) | (np.abs(av - bv) > 1 / 255.0)
    results = {}
    for matte in MATTES:
        bg = np.asarray(matte, dtype=np.float32)
        ca = aa[..., :3] * av[..., None] + bg * (1 - av[..., None])
        cb = bb[..., :3] * bv[..., None] + bg * (1 - bv[..., None])
        delta = np.max(np.abs(ca - cb), axis=2)
        results[','.join(map(str, matte))] = {
            "mean_visible_channel_delta": round(float(delta[support].mean()), 4),
            "edge_changed_gt_12_pct": round(float((delta[edge] > 12).mean() * 100), 4) if edge.any() else None,
        }
    return {
        "same_alpha": bool(np.array_equal(aa[..., 3], bb[..., 3])),
        "alpha_changed_pixels": int(np.count_nonzero(aa[..., 3] != bb[..., 3])),
        "edge_pixels": int(edge.sum()),
        "mattes": results,
        "review_required": bool(np.any(aa[..., 3] != bb[..., 3]) or any(
            v["edge_changed_gt_12_pct"] is not None and v["edge_changed_gt_12_pct"] > 1
            for v in results.values()
        )),
        "quality_improvement_certified": False,
        "note": "Differences on four mattes require visual review and reference alpha; no automatic quality verdict.",
    }
