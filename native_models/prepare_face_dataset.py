"""Prepare private face recovery and detector manifests with explicit consent.

This creates inventories only. It does not upload images, grant rights, or make
third-party face models native to NiyomSilp.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

from native_models.evaluate_sign_v2 import _safe_file

MANIFEST_COLUMNS = [
    "relative_path",
    "task",
    "split",
    "subject_id",
    "consent_scope",
    "rights_holder",
    "rights_proof",
    "sha256",
    "face_bbox",
]
TASKS = {"face_recovery", "face_detection"}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
REQUIRED_CONSENT = "commercial_ai_training"


def _hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _load_consent(consent_path: Path) -> tuple[str, str, str]:
    if not consent_path.is_file():
        raise FileNotFoundError(f"Missing private consent record: {consent_path}")
    try:
        payload = json.loads(consent_path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Consent record must be JSON: {consent_path}") from exc
    subject_id = str(payload.get("subject_id", "")).strip()
    scope = str(payload.get("consent_scope", "")).strip()
    holder = str(payload.get("rights_holder", "")).strip()
    if not subject_id:
        raise ValueError(f"Consent record missing subject_id: {consent_path}")
    if REQUIRED_CONSENT not in {part.strip() for part in scope.split(",")}:
        raise ValueError(
            f"Consent must include {REQUIRED_CONSENT}: {consent_path}"
        )
    if not holder:
        raise ValueError(f"Consent record missing rights_holder: {consent_path}")
    return subject_id, scope, holder


def _validate_bbox(bbox: str | None, relative: str) -> str:
    if not bbox:
        return ""
    parts = [part.strip() for part in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError(f"face_bbox must be x,y,w,h for {relative}")
    values = [int(part) for part in parts]
    if any(value < 0 for value in values) or values[2] <= 0 or values[3] <= 0:
        raise ValueError(f"face_bbox must be positive x,y,w,h for {relative}")
    return ",".join(str(value) for value in values)


def _sidecar_bbox(image_path: Path, relative: str) -> str:
    sidecar = image_path.with_suffix(image_path.suffix + ".json")
    if not sidecar.exists():
        return ""
    try:
        payload = json.loads(sidecar.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Face annotation sidecar must be JSON: {sidecar}") from exc
    return _validate_bbox(payload.get("face_bbox"), relative)


def generate(
    dataset_dir: Path,
    consent_dir: Path,
    *,
    val_fraction: float = 0.2,
    seed: int = 20261012,
    min_side: int = 128,
) -> list[dict]:
    """Build a face manifest for owned portrait recovery and detector work.

    Expected layout:
    dataset_dir/face_recovery/<subject_id>/*.png
    dataset_dir/face_detection/<subject_id>/*.png

    Each subject requires consent_dir/<subject_id>.json with consent_scope
    containing commercial_ai_training. Detector images may include a sidecar
    image.png.json with {"face_bbox": "x,y,w,h"}.
    """
    if not 0 < val_fraction < 1:
        raise ValueError("Validation fraction must be between 0 and 1")
    if min_side <= 0:
        raise ValueError("Minimum image side must be positive")
    root = dataset_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    consent_root = consent_dir.resolve()
    if not consent_root.is_dir():
        raise FileNotFoundError(consent_root)
    files = sorted(path for path in root.rglob("*")
                   if path.is_file() and path.suffix.lower() in EXTENSIONS)
    if not files:
        raise ValueError("No supported face images found")

    consent_cache: dict[str, tuple[str, str, str, str]] = {}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen_hashes: set[str] = set()
    for file in files:
        relative = file.relative_to(root).as_posix()
        parts = Path(relative).parts
        if len(parts) < 3:
            raise ValueError(f"Use task/subject_id/image layout: {relative}")
        task, subject_id = parts[0], parts[1]
        if task not in TASKS:
            raise ValueError(f"Unknown face dataset task: {task}")
        image = _safe_file(root, relative)
        with Image.open(image) as handle:
            im = ImageOps.exif_transpose(handle)
            if min(im.size) < min_side:
                raise ValueError(f"Image below minimum {min_side}px: {relative}")
            im.load()
        digest = _hash_file(image)
        if digest in seen_hashes:
            raise ValueError(f"Duplicate face image content detected: {relative}")
        seen_hashes.add(digest)
        if subject_id not in consent_cache:
            consent_path = consent_root / f"{subject_id}.json"
            consent_subject, scope, holder = _load_consent(consent_path)
            if consent_subject != subject_id:
                raise ValueError(
                    f"Consent subject_id {consent_subject} does not match folder {subject_id}"
                )
            consent_cache[subject_id] = (
                scope,
                holder,
                f"SHA256:{_hash_file(consent_path)}",
                consent_subject,
            )
        scope, holder, proof, _ = consent_cache[subject_id]
        groups[(task, subject_id)].append({
            "relative_path": relative,
            "task": task,
            "subject_id": subject_id,
            "consent_scope": scope,
            "rights_holder": holder,
            "rights_proof": proof,
            "sha256": digest,
            "face_bbox": (
                _sidecar_bbox(image, relative)
                if task == "face_detection"
                else ""
            ),
        })

    rows: list[dict] = []
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            raise ValueError(f"Need at least two images for train/validation in {key}")
        selected = list(items)
        random.Random(f"{seed}:{key[0]}:{key[1]}").shuffle(selected)
        n_val = max(1, min(len(items) - 1, round(len(items) * val_fraction)))
        for i, record in enumerate(selected):
            rows.append({**record, "split": "val" if i < n_val else "train"})
    return sorted(
        rows,
        key=lambda row: (row["task"], row["subject_id"], row["relative_path"]),
    )


def write_manifest(records: list[dict], output: Path):
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing face manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description="Create local face/detector consent manifests")
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--consent-dir", required=True)
    parser.add_argument("--output", required=True, help="Private manifest CSV path")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--confirm-consent", action="store_true", required=True,
                        help="Confirm every subject consent permits commercial AI training")
    args = parser.parse_args()
    records = generate(
        Path(args.dataset_dir),
        Path(args.consent_dir),
        val_fraction=args.validation_fraction,
        seed=args.seed,
    )
    write_manifest(records, Path(args.output))
    print(
        f"Face manifest created locally: {sum(r['split']=='train' for r in records)} train, "
        f"{sum(r['split']=='val' for r in records)} val. Keep consent records private."
    )


if __name__ == "__main__":
    main()
