"""Offline, from-scratch trainer for the experimental NiyomSilp SR model.

No input pictures or checkpoint weights are downloaded automatically. The
rights-checked CSV inventory is mandatory before training.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from native_models.niyomsil_sr import MODEL_ID, create_model
from native_models.prepare_dataset import _pixel_fingerprint


REQUIRED = {"relative_path", "rights_holder", "license", "rights_proof", "sha256", "split"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_inventory(csv_path: Path, image_dir: Path) -> dict[str, list[Path]]:
    """Require an auditable license/rightsholder record for every training image."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing training inventory: {csv_path}")
    root = image_dir.resolve()
    groups: dict[str, list[Path]] = {"train": [], "val": []}
    used_paths: set[Path] = set()
    hash_splits: dict[str, str] = {}
    pixel_splits: dict[str, str] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError(f"Training manifest requires columns: {sorted(REQUIRED)}")
        for number, row in enumerate(reader, start=2):
            if not all((row.get(name) or "").strip() for name in REQUIRED):
                raise ValueError(f"Missing dataset provenance field at CSV line {number}")
            split = row["split"].strip().lower()
            if split not in groups:
                raise ValueError(f"Invalid split at line {number}: {split}")
            relative = Path(row["relative_path"].strip())
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe path at CSV line {number}")
            image_path = (root / relative).resolve()
            if image_path != root and root not in image_path.parents:
                raise ValueError(f"Path escaped training directory at CSV line {number}")
            if image_path in used_paths:
                raise ValueError(f"Duplicate image at CSV line {number}")
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            digest = file_hash(image_path)
            if digest != row["sha256"].strip().lower():
                raise ValueError(f"SHA256 mismatch for {image_path.name}")
            if digest in hash_splits and hash_splits[digest] != split:
                raise ValueError("Identical image in train and validation (data leakage)")
            hash_splits[digest] = split
            pixel_hash = _pixel_fingerprint(image_path)
            if pixel_hash in pixel_splits:
                if pixel_splits[pixel_hash] != split:
                    raise ValueError("Identical decoded pixels in train and validation (data leakage)")
                raise ValueError("Duplicate decoded image pixels within a split")
            pixel_splits[pixel_hash] = split
            used_paths.add(image_path)
            groups[split].append(image_path)
    if not groups["train"] or not groups["val"]:
        raise ValueError("Manifest must contain at least one train and one val image")
    return groups


def make_pair(path: Path, patch: int, scale: int, rng: random.Random, *, train: bool):
    """Create aligned HR/LR patches using known bicubic degradation.

    This synthetic degradation is a baseline only. Later training will need
    separately verified, real camera/AI/print degradation pairs.
    """
    with Image.open(path) as src:
        high = ImageOps.exif_transpose(src).convert("RGB")
    if high.width < patch or high.height < patch:
        raise ValueError(f"Image too small for {patch}px patch: {path.name}")
    x = rng.randint(0, high.width - patch) if train else (high.width - patch) // 2
    y = rng.randint(0, high.height - patch) if train else (high.height - patch) // 2
    high = high.crop((x, y, x + patch, y + patch))
    if train and rng.randrange(2):
        high = ImageOps.mirror(high)
    if train and rng.randrange(2):
        high = ImageOps.flip(high)
    low = high.resize((patch // scale, patch // scale), Image.Resampling.BICUBIC)
    def as_tensor(image):
        return torch.from_numpy(np.array(image, dtype=np.float32).copy()).permute(2, 0, 1) / 255.0
    return as_tensor(low), as_tensor(high)


def edge_loss(predicted, target):
    return (
        (predicted[:, :, 1:] - predicted[:, :, :-1] -
         target[:, :, 1:] + target[:, :, :-1]).abs().mean()
        +
        (predicted[:, :, :, 1:] - predicted[:, :, :, :-1] -
         target[:, :, :, 1:] + target[:, :, :, :-1]).abs().mean()
    )


def train(args):
    image_dir = Path(args.data_dir)
    manifest = Path(args.manifest)
    groups = load_inventory(manifest, image_dir)
    if args.patch % args.scale != 0 or args.patch < args.scale * 8:
        raise ValueError("HR patch must be divisible by scale and at least scale*8 pixels")
    rng = random.Random(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else "cpu" if args.device == "auto" else args.device)
    model = create_model(scale=args.scale, channels=args.channels, blocks=args.blocks).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    best = float("inf")
    for epoch in range(1, args.epochs + 1):
        model.train()
        shuffled = groups["train"][:]
        rng.shuffle(shuffled)
        total_loss, count = 0.0, 0
        for start in range(0, len(shuffled), args.batch_size):
            paths = shuffled[start:start + args.batch_size]
            pairs = [make_pair(p, args.patch, args.scale, rng, train=True) for p in paths]
            low = torch.stack([p[0] for p in pairs]).to(device)
            high = torch.stack([p[1] for p in pairs]).to(device)
            optimizer.zero_grad(set_to_none=True)
            output = model(low)
            loss = (output - high).abs().mean() + 0.1 * edge_loss(output, high)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(loss.detach()) * len(paths)
            count += len(paths)

        model.eval()
        validation, vcount = 0.0, 0
        with torch.no_grad():
            for path in groups["val"]:
                low, high = make_pair(path, args.patch, args.scale, rng, train=False)
                output = model(low.unsqueeze(0).to(device))
                validation += float((output.cpu() - high.unsqueeze(0)).abs().mean())
                vcount += 1
        score = validation / vcount
        print(f"epoch={epoch} train_loss={total_loss/count:.6f} val_mae={score:.6f}")
        if score < best:
            best = score
            checkpoint = {
                "model_id": MODEL_ID,
                "training_origin": "random_initialization_no_upstream_checkpoint",
                "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                "config": {"scale": args.scale, "channels": args.channels, "blocks": args.blocks},
                "epoch": epoch, "seed": args.seed,
                "validation_mae": best,
                "inventory_sha256": file_hash(manifest),
            }
            dest = output_dir / f"{MODEL_ID}-x{args.scale}-experimental.pth"
            torch.save(checkpoint, dest)

    record = {
        "model_id": MODEL_ID,
        "status": "experimental_NOT_approved_for_production",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "training_origin": "random_initialization_no_upstream_checkpoint",
        "train_files": len(groups["train"]),
        "validation_files": len(groups["val"]),
        "inventory_sha256": file_hash(manifest),
        "checkpoint": dest.name,
        "checkpoint_sha256": file_hash(dest),
        "config": checkpoint["config"],
        "best_validation_mae": best,
        "notes": "Asset rights are recorded in the supplied CSV; evidence still requires human audit.",
    }
    (output_dir / "TRAINING_PROVENANCE.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved experimental checkpoint and auditable provenance:", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Train experimental NiyomSilp super-resolution from scratch")
    parser.add_argument("--manifest", required=True, help="Rights inventory CSV; no images fetched automatically")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scale", type=int, choices=(2, 4), default=4)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--patch", type=int, default=128)
    parser.add_argument("--channels", type=int, default=48)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--lr", type=float, default=0.0001)
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--device", default="auto", help="auto/cpu/cuda; no DirectML training support")
    args = parser.parse_args()
    if args.epochs <= 0 or args.batch_size <= 0 or args.lr <= 0:
        parser.error("epochs, batch size and learning rate must be positive")
    train(args)


if __name__ == "__main__":
    main()
