"""Fine-tune the upstream Real-ESRGAN x4plus checkpoint for NiyomSilp signage.

Experimental v2 tooling; NEVER switches v1's runtime or overwrites its weights.
The output is a DERIVATIVE of an externally pretrained model, not fully owned IP.
Requires human-reviewed, licensed local image data and checkpoint terms.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from native_models.train_sr import file_hash, load_inventory, make_pair


MODEL_ID = "niyomsil-sign-ai-v2"
UPSTREAM_MODEL = "RealESRGAN_x4plus"
UPSTREAM_LICENSE = "BSD-3-Clause (source code; verify checkpoint terms independently)"
UPSTREAM_URL = "https://github.com/xinntao/Real-ESRGAN"


def validate_rights_review(path: Path) -> dict:
    """A required human attestation; NOT an automated legal clearance."""
    data = json.loads(path.read_text(encoding="utf-8"))
    needed = ("reviewer", "reviewed_at", "upstream_checkpoint_url",
              "upstream_checkpoint_license", "commercial_use_approved",
              "dataset_rights_confirmed")
    if any(not data.get(field) for field in needed):
        raise ValueError("Rights review incomplete; see docs/V2_MODEL_RIGHTS_TH.md")
    if data["commercial_use_approved"] is not True or data["dataset_rights_confirmed"] is not True:
        raise ValueError("Commercial checkpoint and training-image rights not approved")
    return data


def load_base_checkpoint(model: nn.Module, path: Path):
    """Use safe tensor-only deserialization; explicitly load exact x4plus architecture."""
    if not path.is_file():
        raise FileNotFoundError(path)
    checkpoint = torch.load(str(path), map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Upstream checkpoint must be a dict")
    key = "params_ema" if "params_ema" in checkpoint else "params"
    if key not in checkpoint or not isinstance(checkpoint[key], dict):
        raise ValueError("Expected RealESRGAN_x4plus params_ema / params state dictionary")
    model.load_state_dict(checkpoint[key], strict=True)
    return key


def psnr(output, target):
    mse = F.mse_loss(output, target).clamp_min(1e-12)
    return float(-10.0 * torch.log10(mse))


def evaluate(model, paths, patch, scale, seed, device):
    """Deterministic per-image validation with a bicubic comparison."""
    rng = random.Random(seed)
    model.eval()
    predictions, baselines = [], []
    with torch.inference_mode():
        for image_path in paths:
            lr, hr = make_pair(image_path, patch, scale, rng, train=False)
            lr, hr = lr.unsqueeze(0).to(device), hr.unsqueeze(0).to(device)
            guess = model(lr).clamp(0, 1)
            bicubic = F.interpolate(lr, size=hr.shape[-2:], mode="bicubic",
                                    align_corners=False).clamp(0, 1)
            predictions.append(psnr(guess, hr))
            baselines.append(psnr(bicubic, hr))
    return sum(predictions) / len(predictions), sum(baselines) / len(baselines)


def run(args):
    if args.scale != 4:
        raise ValueError("This pretrained x4plus fine-tuner supports scale=4 only")
    if args.patch < 32 or args.patch % args.scale:
        raise ValueError("HR training patch must be >= 32 and divisible by 4")
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0:
        raise ValueError("epochs, batch size and learning rate must be positive")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available")

    rights_path = Path(args.rights_review).resolve()
    rights = validate_rights_review(rights_path)
    paths = load_inventory(Path(args.manifest), Path(args.data_dir))
    pretrained_path = Path(args.pretrained).resolve()
    pretrained_hash = file_hash(pretrained_path)
    if pretrained_hash.lower() != args.pretrained_sha256.lower():
        raise ValueError("Real-ESRGAN pretrained weight SHA256 mismatch")
    if not args.allow_pretrained_derivative:
        raise ValueError("Explicit --allow-pretrained-derivative flag required")

    from basicsr.archs.rrdbnet_arch import RRDBNet
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=23, num_grow_ch=32, scale=4)
    source_key = load_base_checkpoint(model, pretrained_path)
    device = torch.device(
        ("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto" else args.device
    )
    model.to(device)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.00001)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    baseline_psnr, bicubic_psnr = evaluate(
        model, paths["val"], args.patch, args.scale, args.seed, device
    )
    print(f"Upstream baseline PSNR: {baseline_psnr:.3f}; bicubic: {bicubic_psnr:.3f}")
    best_psnr = baseline_psnr
    best_checkpoint = None
    run_log = []
    for epoch in range(1, args.epochs + 1):
        train_paths = list(paths["train"])
        rng.shuffle(train_paths)
        model.train()
        losses = []
        for start in range(0, len(train_paths), args.batch_size):
            selected = train_paths[start:start + args.batch_size]
            lr_hr = [make_pair(p, args.patch, args.scale, rng, train=True) for p in selected]
            lr = torch.stack([pair[0] for pair in lr_hr]).to(device)
            hr = torch.stack([pair[1] for pair in lr_hr]).to(device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(lr)
            # Prefer faithful contours/color, not hallucinated edges.
            loss = F.l1_loss(prediction, hr)
            loss += 0.05 * (
                F.l1_loss(prediction[..., 1:, :]-prediction[..., :-1, :],
                          hr[..., 1:, :]-hr[..., :-1, :])
                + F.l1_loss(prediction[..., 1:]-prediction[..., :-1],
                            hr[..., 1:]-hr[..., :-1])
            )
            if not torch.isfinite(loss):
                raise FloatingPointError("Non-finite training loss")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        val_psnr, _ = evaluate(model, paths["val"], args.patch, args.scale, args.seed, device)
        record = {"epoch": epoch, "train_loss": sum(losses)/len(losses),
                  "validation_psnr": val_psnr}
        run_log.append(record)
        print(json.dumps(record))
        # Only save a candidate if it improves this reproducible validation set.
        if val_psnr > best_psnr:
            best_psnr = val_psnr
            best_checkpoint = output_dir / f"{MODEL_ID}-x4-CANDIDATE.pth"
            tmp_path = best_checkpoint.with_suffix(".pth.tmp")
            torch.save({"params_ema": {key: value.detach().cpu()
                                     for key, value in model.state_dict().items()}}, tmp_path)
            tmp_path.replace(best_checkpoint)

    status = ("candidate_requires_quality_and_rights_approval"
              if best_checkpoint is not None else "no_improvement_no_checkpoint")
    report = {
        "model_id": MODEL_ID, "status": status,
        "origin": "FINE_TUNED_FROM_THIRD_PARTY_PRETRAINED_WEIGHTS",
        "upstream_name": UPSTREAM_MODEL, "upstream_url": UPSTREAM_URL,
        "upstream_source_license": UPSTREAM_LICENSE,
        "upstream_checkpoint_url_reviewed": rights["upstream_checkpoint_url"],
        "upstream_checkpoint_license_reviewed": rights["upstream_checkpoint_license"],
        "upstream_checkpoint_sha256": pretrained_hash, "source_state_key": source_key,
        "rights_review_sha256": file_hash(rights_path),
        "training_manifest_sha256": file_hash(Path(args.manifest)),
        "training_images": len(paths["train"]), "validation_images": len(paths["val"]),
        "base_validation_psnr": baseline_psnr, "bicubic_validation_psnr": bicubic_psnr,
        "best_validation_psnr": best_psnr,
        "checkpoint": best_checkpoint.name if best_checkpoint else None,
        "checkpoint_sha256": file_hash(best_checkpoint) if best_checkpoint else None,
        "training_log": run_log,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "important": "DERIVATIVE model; upstream rights and third-party notices persist. "
                     "Not qualified for production without Windows sign-print visual evaluation.",
    }
    (output_dir / "PROVENANCE_V2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Fine-tuning complete. Result:", status)


def main():
    p = argparse.ArgumentParser(
        description="Experimentally fine-tune RealESRGAN_x4plus for NiyomSilp Design v2."
    )
    p.add_argument("--pretrained", required=True, help="Path to pinned external x4plus .pth")
    p.add_argument("--pretrained-sha256", required=True, help="Expected 64-char checksum")
    p.add_argument("--rights-review", required=True, help="Human-reviewed JSON file")
    p.add_argument("--manifest", required=True, help="Rights-checked train/val image CSV")
    p.add_argument("--data-dir", required=True, help="Local private dataset folder")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--allow-pretrained-derivative", action="store_true",
                   help="Acknowledge tuned weights remain based on upstream weights")
    p.add_argument("--scale", type=int, choices=(4,), default=4)
    p.add_argument("--patch", type=int, default=128)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--lr", type=float, default=0.00001)
    p.add_argument("--seed", type=int, default=20261012)
    p.add_argument("--device", default="auto", help="auto/cpu/cuda; GPU strongly recommended")
    args = p.parse_args()
    if len(args.pretrained_sha256) != 64 or any(
        c not in "0123456789abcdefABCDEF" for c in args.pretrained_sha256
    ):
        p.error("--pretrained-sha256 must be a valid 64-character hexadecimal SHA256")
    run(args)


if __name__ == "__main__":
    main()
