"""Run an experimental NiyomSilp SR checkpoint on local images.

This is for v2 research checkpoints trained by ``native_models.train_sr``.
It does not download weights and does not replace the approved v1 runtime.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from native_models.niyomsil_sr import MODEL_ID, create_model


def _as_rgb_tensor(image: Image.Image) -> torch.Tensor:
    pixels = np.array(image.convert("RGB"), dtype=np.float32).copy()
    return torch.from_numpy(pixels).permute(2, 0, 1).unsqueeze(0) / 255.0


def _from_rgb_tensor(tensor: torch.Tensor) -> Image.Image:
    pixels = (
        tensor.squeeze(0).detach().cpu().clamp(0, 1).permute(1, 2, 0).numpy() * 255.0
    ).round().astype(np.uint8)
    return Image.fromarray(pixels, "RGB")


def load_checkpoint(path: Path, device: torch.device):
    """Load only NiyomSilp-from-scratch checkpoints with their recorded config."""
    checkpoint = torch.load(path, map_location=device)
    if checkpoint.get("model_id") != MODEL_ID:
        raise ValueError(f"Unsupported checkpoint model_id: {checkpoint.get('model_id')!r}")
    if checkpoint.get("training_origin") != "random_initialization_no_upstream_checkpoint":
        raise ValueError("Refusing checkpoint that was not recorded as trained from scratch")
    config = checkpoint.get("config") or {}
    model = create_model(
        scale=int(config.get("scale", 4)),
        channels=int(config.get("channels", 48)),
        blocks=int(config.get("blocks", 6)),
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model


def upscale_image(input_path: Path, checkpoint_path: Path, output_path: Path,
                  *, device_name: str = "auto") -> Path:
    device = torch.device(
        "cuda" if device_name == "auto" and torch.cuda.is_available()
        else "cpu" if device_name == "auto" else device_name
    )
    model = load_checkpoint(checkpoint_path, device)
    scale = int(model.scale)
    with Image.open(input_path) as source:
        image = ImageOps.exif_transpose(source)
        alpha = None
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            alpha = image.convert("RGBA").getchannel("A")
        rgb = image.convert("RGB")

    with torch.no_grad():
        output = model(_as_rgb_tensor(rgb).to(device))
    result = _from_rgb_tensor(output)
    if alpha is not None:
        alpha = alpha.resize(
            (alpha.width * scale, alpha.height * scale),
            Image.Resampling.BICUBIC,
        )
        result = result.convert("RGBA")
        result.putalpha(alpha)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Run an experimental NiyomSilp SR checkpoint")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint produced by native_models.train_sr")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto", help="auto/cpu/cuda")
    args = parser.parse_args()
    saved = upscale_image(
        Path(args.input), Path(args.checkpoint), Path(args.output), device_name=args.device
    )
    print(f"Saved v2 experimental output: {saved}")


if __name__ == "__main__":
    main()
