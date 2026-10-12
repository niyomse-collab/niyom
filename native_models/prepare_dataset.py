"""Create local, reproducible image manifests for v2 without uploading images.

Input layout: images/thai_text/*.png, images/logo/*.png,
images/flat_color/*.png, images/photograph/*.png, images/portrait/*.png.
The caller attests to having training rights; this tool cannot grant rights.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

from native_models.evaluate_sign_v2 import CATEGORIES, _safe_file

MANIFEST_COLUMNS = [
    "relative_path", "category", "split", "rights_holder",
    "license", "rights_proof", "sha256",
]
EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _pixel_fingerprint(path: Path) -> str:
    """Fingerprint decoded RGB pixels, not metadata or PNG compression bytes."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            alpha = image.convert("RGBA").getchannel("A")
            if alpha.getextrema()[0] != 255:
                raise ValueError(
                    f"Transparent training image: {path.name}. "
                    "Flatten onto a documented background before RGB training."
                )
        rgb = image.convert("RGB")
        digest = hashlib.sha256()
        digest.update(rgb.width.to_bytes(8, "big"))
        digest.update(rgb.height.to_bytes(8, "big"))
        for y in range(rgb.height):
            digest.update(rgb.crop((0, y, rgb.width, y + 1)).tobytes())
        return digest.hexdigest()


def generate(image_dir: Path, rights_holder: str, license_name: str, evidence: Path,
             *, val_fraction: float = 0.2, seed: int = 20261012,
             min_side: int = 64) -> list[dict]:
    """Create a dataset inventory with train/validation separation per category.

    Require two distinct originals in each included category. Images must be
    local and owned/licensed for the intended AI training purpose.
    """
    if not rights_holder.strip() or not license_name.strip():
        raise ValueError("Rights holder and real licensing terms must be supplied")
    if not 0 < val_fraction < 1:
        raise ValueError("Validation fraction must be between 0 and 1")
    if min_side <= 0:
        raise ValueError("Minimum image side must be positive")
    if not evidence.is_file():
        raise FileNotFoundError(f"Missing PRIVATE rights evidence: {evidence}")
    evidence_hash = _hash_file(evidence)
    root = image_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    files = sorted(path for path in root.rglob("*")
                   if path.is_file() and path.suffix.lower() in EXTENSIONS)
    if not files:
        raise ValueError("No supported image files found")
    groups: dict[str, list[dict]] = defaultdict(list)
    seen_hashes: set[str] = set()
    seen_pixels: set[str] = set()
    for file in files:
        relative = file.relative_to(root).as_posix()
        category = relative.split("/")[0].lower()
        if category not in CATEGORIES or len(Path(relative).parts) < 2:
            raise ValueError(f"Place every image in a named category folder: {relative}")
        image = _safe_file(root, relative)
        with Image.open(image) as handle:
            im = ImageOps.exif_transpose(handle)
            if min(im.size) < min_side:
                raise ValueError(f"Image below minimum {min_side}px: {relative}")
            im.load()  # Fully decode while the source file is still open.
        digest = _hash_file(image)
        if digest in seen_hashes:
            raise ValueError(f"Duplicate image content detected: {relative}")
        seen_hashes.add(digest)
        pixel_digest = _pixel_fingerprint(image)
        if pixel_digest in seen_pixels:
            raise ValueError(f"Duplicate decoded image pixels: {relative}")
        seen_pixels.add(pixel_digest)
        groups[category].append({
            "relative_path": relative, "category": category,
            "rights_holder": rights_holder.strip(),
            "license": license_name.strip(),
            "rights_proof": f"SHA256:{evidence_hash}",
            "sha256": digest,
        })
    rows = []
    for category, items in sorted(groups.items()):
        if len(items) < 2:
            raise ValueError(f"Need at least two images for train/validation in {category}")
        selected = list(items)
        random.Random(f"{seed}:{category}").shuffle(selected)
        n_val = max(1, min(len(items) - 1, round(len(items) * val_fraction)))
        for i, record in enumerate(selected):
            rows.append({**record, "split": "val" if i < n_val else "train"})
    return sorted(rows, key=lambda row: (row["category"], row["relative_path"]))


def write_manifests(records: list[dict], all_manifest: Path, val_manifest: Path):
    if all_manifest.resolve() == val_manifest.resolve():
        raise ValueError("Training and benchmark manifests must use different paths")
    if all_manifest.exists() or val_manifest.exists():
        raise FileExistsError("Refusing to overwrite an existing training manifest")
    for target, rows in (
        (all_manifest, records),
        (val_manifest, [r for r in records if r["split"] == "val"]),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description="Create rights-inventoried local v2 training manifests")
    p.add_argument("--image-dir", required=True)
    p.add_argument("--rights-holder", required=True)
    p.add_argument("--license", required=True)
    p.add_argument("--evidence", required=True, help="Private record of training rights; never upload it")
    p.add_argument("--output", required=True, help="Private manifest.csv path")
    p.add_argument("--benchmark-output", required=True, help="Validation-only CSV")
    p.add_argument("--validation-fraction", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=20261012)
    p.add_argument("--confirm-rights", action="store_true", required=True,
                   help="Confirm rights to train models for commercial shop use")
    args = p.parse_args()
    inventory = generate(
        Path(args.image_dir), args.rights_holder, args.license,
        Path(args.evidence), val_fraction=args.validation_fraction, seed=args.seed
    )
    write_manifests(inventory, Path(args.output), Path(args.benchmark_output))
    print(f"Manifests created locally: {sum(x['split']=='train' for x in inventory)} train, "
          f"{sum(x['split']=='val' for x in inventory)} val. Rights still require human verification.")


if __name__ == "__main__":
    main()
