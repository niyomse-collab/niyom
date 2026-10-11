"""Offline quality-gate for NiyomSilp Design v2 signage candidates.

Compares *matching full-resolution* reference / stable-v1 / experimental-v2
outputs. Does not download images, alter originals, or approve production.
No pytorch required. The images and metrics stay on the local machine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

CATEGORIES = {"thai_text", "logo", "flat_color", "photograph", "portrait"}
FIELDS = {"relative_path", "category", "split", "rights_holder",
          "license", "rights_proof", "sha256"}


def _file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _safe_file(directory: Path, name: str) -> Path:
    relative = Path(name)
    if (not name or relative.is_absolute() or ".." in relative.parts
            or relative == Path(".") or relative.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        raise ValueError(f"Invalid image relative_path: {name}")
    root = directory.resolve()
    candidate = (root / relative).resolve()
    if root not in candidate.parents:
        raise ValueError(f"Unsafe or escaping image path: {name}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _load_manifest(manifest: Path, references: Path) -> list[tuple[str, str]]:
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    data, names = [], set()
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError(f"Benchmark CSV must have columns: {sorted(FIELDS)}")
        for line, row in enumerate(reader, start=2):
            if not all((row.get(k) or "").strip() for k in FIELDS):
                raise ValueError(f"Missing benchmark CSV field at line {line}")
            if row["split"].strip().lower() != "val":
                raise ValueError("Only held-out validation images are allowed in benchmark")
            name = row["relative_path"].strip()
            if name in names:
                raise ValueError("Duplicate validation path")
            names.add(name)
            category = row["category"].strip().lower()
            if category not in CATEGORIES:
                raise ValueError(f"Unrecognized benchmark category: {category}")
            reference = _safe_file(references, name)
            actual_hash = _file_sha256(reference)
            if actual_hash != row["sha256"].strip().lower():
                raise ValueError(f"Reference checksum mismatch: {name}")
            data.append((name, category))
    if not data:
        raise ValueError("Validation benchmark cannot be empty")
    return data


def _rgb(path: Path) -> np.ndarray:
    with Image.open(path) as file:
        image = ImageOps.exif_transpose(file).convert("RGB")
        return np.asarray(image, dtype=np.float32) / 255.0


def _luma(image: np.ndarray) -> np.ndarray:
    return (image[..., 0] * 0.2126 + image[..., 1] * 0.7152
            + image[..., 2] * 0.0722)


def _edge_error(reference: np.ndarray, output: np.ndarray) -> float:
    if min(reference.shape[:2]) < 2:
        raise ValueError("Benchmark images must be at least 2x2 pixels")
    ref, test = _luma(reference), _luma(output)
    dx = np.abs(np.diff(ref, axis=1) - np.diff(test, axis=1)).mean()
    dy = np.abs(np.diff(ref, axis=0) - np.diff(test, axis=0)).mean()
    return float((dx + dy) / 2)


def _flat_error(reference: np.ndarray, output: np.ndarray) -> float | None:
    grey = _luma(reference)
    # Suppress boundaries of flat fields. No OCR claims or invented edges.
    gx = np.zeros_like(grey)
    gy = np.zeros_like(grey)
    gx[:, 1:] = np.abs(np.diff(grey, axis=1))
    gy[1:, :] = np.abs(np.diff(grey, axis=0))
    mask = (gx < 2/255) & (gy < 2/255)
    if not np.any(mask):
        return None
    return float(np.abs(reference - output)[mask].mean())


def _metrics(reference: np.ndarray, output: np.ndarray) -> dict:
    if reference.shape != output.shape:
        raise ValueError(f"Image dimensions differ: reference={reference.shape}, output={output.shape}")
    mae = float(np.abs(reference - output).mean())
    mse = float(np.square(reference - output).mean())
    return {
        "psnr_db": round(float(-10 * np.log10(max(mse, 1e-12))), 5),
        "rgb_mae": round(mae, 7),
        "edge_mae": round(_edge_error(reference, output), 7),
        "mean_color_bias": round(float(
            np.abs(reference.mean(axis=(0, 1)) - output.mean(axis=(0, 1))).mean()), 7),
        "flat_region_mae": None if (flat := _flat_error(reference, output)) is None else round(flat, 7),
    }


def evaluate(manifest: Path, reference_dir: Path, v1_dir: Path, v2_dir: Path,
             *, psnr_tolerance_db: float = 0.1, edge_tolerance: float = 0.005,
             min_psnr_gain_db: float = 0.05) -> dict:
    if psnr_tolerance_db < 0 or edge_tolerance < 0 or min_psnr_gain_db <= 0:
        raise ValueError("Quality thresholds must be nonnegative and gain must be positive")
    resolved = [p.resolve() for p in (reference_dir, v1_dir, v2_dir)]
    if len(set(resolved)) != 3:
        raise ValueError("Reference, v1 and v2 must use three separate directories")
    samples = _load_manifest(manifest, reference_dir)
    records = []
    for name, category in samples:
        ref = _rgb(_safe_file(reference_dir, name))
        v1 = _rgb(_safe_file(v1_dir, name))
        v2 = _rgb(_safe_file(v2_dir, name))
        m1, m2 = _metrics(ref, v1), _metrics(ref, v2)
        regression = (
            m2["psnr_db"] < m1["psnr_db"] - psnr_tolerance_db
            or m2["edge_mae"] > m1["edge_mae"] + edge_tolerance
            or m2["mean_color_bias"] > m1["mean_color_bias"] + edge_tolerance
            or (m1["flat_region_mae"] is not None
                and m2["flat_region_mae"] is not None
                and m2["flat_region_mae"] > m1["flat_region_mae"] + edge_tolerance)
        )
        records.append({
            "relative_path": name, "category": category,
            "v1": m1, "v2": m2, "regression": regression,
            "psnr_gain_db": round(m2["psnr_db"] - m1["psnr_db"], 5),
        })
    gain = sum(r["psnr_gain_db"] for r in records) / len(records)
    by_category = defaultdict(list)
    for row in records:
        by_category[row["category"]].append(row)
    summary = {
        category: {
            "count": len(rows),
            "mean_psnr_gain_db": round(sum(r["psnr_gain_db"] for r in rows) / len(rows), 5),
            "regression_count": sum(r["regression"] for r in rows),
        } for category, rows in sorted(by_category.items())
    }
    # Quantitative eligibility does not replace a real Thai-text/face check or print proof.
    passed = gain >= min_psnr_gain_db and not any(r["regression"] for r in records)
    return {
        "status": ("eligible_for_human_print_review" if passed
                   else "rejected_by_automated_quality_gate"),
        "production_approved": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "reference_manifest_sha256": _file_sha256(manifest),
        "image_count": len(records),
        "mean_psnr_gain_db": round(gain, 5),
        "thresholds": {
            "min_mean_psnr_gain_db": min_psnr_gain_db,
            "max_per_image_psnr_regression_db": psnr_tolerance_db,
            "max_per_image_edge_color_regression": edge_tolerance,
        },
        "by_category": summary,
        "images": records,
        "limitations": "PSNR and pixel edges cannot prove Thai spelling, face identity, "
                       "print color accuracy or perceived quality. Human tests required.",
    }


def main():
    parser = argparse.ArgumentParser(description="Compare full-resolution v1/v2 signage outputs offline")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--reference-dir", required=True)
    parser.add_argument("--v1-dir", required=True)
    parser.add_argument("--v2-dir", required=True)
    parser.add_argument("--report", required=True, help="Local JSON; do not commit customer information")
    args = parser.parse_args()
    report = evaluate(
        Path(args.manifest), Path(args.reference_dir),
        Path(args.v1_dir), Path(args.v2_dir)
    )
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "image_count": report["image_count"],
                      "mean_psnr_gain_db": report["mean_psnr_gain_db"],
                      "report": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
