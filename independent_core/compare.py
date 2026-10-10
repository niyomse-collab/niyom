"""Quantitative baseline-vs-candidate PNG test; no subjective quality claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def compare_png(baseline: str | Path, candidate: str | Path) -> dict:
    with Image.open(baseline) as a, Image.open(candidate) as b:
        left = np.asarray(a.convert("RGBA"), dtype=np.uint8)
        right = np.asarray(b.convert("RGBA"), dtype=np.uint8)
    if left.shape != right.shape:
        return {"same_dimensions": False, "same_pixels": False,
                "baseline_shape": list(left.shape), "candidate_shape": list(right.shape)}
    delta = np.abs(left.astype(np.int16) - right.astype(np.int16))
    mse = np.mean(np.square(delta.astype(np.float64)))
    return {
        "same_dimensions": True,
        "same_pixels": bool(np.array_equal(left, right)),
        "changed_pixels": int(np.count_nonzero(np.any(delta != 0, axis=2))),
        "max_difference": int(delta.max()),
        "mean_absolute_difference": float(delta.mean()),
        "psnr_db": None if mse == 0 else round(float(10 * np.log10(255.0 ** 2 / mse)), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ARM baseline and NiyomSilp experimental outputs")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    report = compare_png(args.baseline, args.candidate)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["same_pixels"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
