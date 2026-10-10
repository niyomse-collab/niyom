"""NiyomSilp independent experiment using officially published Real-ESRGAN APIs.

This is new application glue, NOT a copy of ARM engine source. Keep the exact
legacy inference recipe until pixel parity is proven: RRDBNet x4plus, FP32,
tile 256 / pad 10 / pre-pad 0, two 4x+2x passes for 8x.

IMPORTANT: Existing ARM engine passed RGB PIL arrays directly to RealESRGANer
and treated returned arrays as RGB; despite RealESRGAN's BGR convention this
is the observable baseline. Preserve that channel path *for parity* here.
Changing RGB/BGR conventions needs separate user-approved color tests.

No current UI or processing path imports this experimental package.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[int], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True)
class CoreConfig:
    model_path: str | Path
    device: str = "auto"
    tile: int = 256
    tile_pad: int = 10
    pre_pad: int = 0
    fp16: bool = False

    def validate(self) -> None:
        model = Path(self.model_path)
        if not model.is_file():
            raise FileNotFoundError(f"Model weights not found: {model}")
        if self.tile < 0 or self.tile_pad < 0 or self.pre_pad < 0:
            raise ValueError("Tile parameters must not be negative")
        if self.device not in ("auto", "cpu", "cuda") and not self.device.startswith("cuda:"):
            raise ValueError("Unsupported experimental device")


class IndependentCore:
    """Core-owned adapter whose API resembles the existing engine interface."""

    def __init__(self, config: CoreConfig):
        config.validate()
        self.config = config
        self._upsampler = None

    def _get_upsampler(self):
        if self._upsampler is None:
            import torch
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer

            device_name = ("cuda" if torch.cuda.is_available() else "cpu") if self.config.device == "auto" else self.config.device
            device = torch.device(device_name)
            network = RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64,
                num_block=23, num_grow_ch=32, scale=4
            )
            self._upsampler = RealESRGANer(
                scale=4, model_path=str(self.config.model_path), model=network,
                tile=self.config.tile, tile_pad=self.config.tile_pad,
                pre_pad=self.config.pre_pad,
                half=bool(self.config.fp16 and device.type == "cuda"),
                device=device,
            )
        return self._upsampler

    @staticmethod
    def _cancel_if_requested(check: CancelCheck | None) -> None:
        if check and check():
            raise InterruptedError("Image processing cancelled")

    def _pass(self, pixels, scale: int, lo: int, hi: int,
              progress_callback: ProgressCallback | None,
              cancel_check: CancelCheck | None):
        self._cancel_if_requested(cancel_check)
        upsampler = self._get_upsampler()
        handle = None
        if progress_callback and hasattr(upsampler, "model") and hasattr(upsampler.model, "register_forward_hook"):
            height, width = pixels.shape[:2]
            tile = int(getattr(upsampler, "tile_size", 0) or 0)
            total = math.ceil(width / tile) * math.ceil(height / tile) if tile else 1
            done = [0]

            def after_tile(_model, _inputs, _outputs):
                self._cancel_if_requested(cancel_check)
                done[0] += 1
                progress_callback(min(hi, lo + round((hi - lo) * done[0] / total)))

            handle = upsampler.model.register_forward_hook(after_tile)
        try:
            result, _ = upsampler.enhance(pixels, outscale=scale)
        finally:
            if handle is not None:
                handle.remove()
        self._cancel_if_requested(cancel_check)
        if progress_callback:
            progress_callback(hi)
        return result

    def enhance(self, input_path: str | Path, output_path: str | Path,
                scale: int = 4, progress_callback: ProgressCallback | None = None,
                cancel_check: CancelCheck | None = None) -> dict:
        """Experimental PNG output; never overwrites the original photo."""
        import numpy as np
        from PIL import Image

        if scale not in (2, 4, 8):
            raise ValueError("Only 2x, 4x and 8x are supported")
        source, dest = Path(input_path), Path(output_path)
        if dest.suffix.lower() != ".png":
            raise ValueError("Experimental output must be PNG")
        if source.resolve() == dest.resolve():
            raise ValueError("Refusing to overwrite input")
        self._cancel_if_requested(cancel_check)
        with Image.open(source) as original:
            original_size = original.size
            if original.mode not in ("RGB", "RGBA"):
                original = original.convert("RGB")
            # Intentionally NO RGB/BGR swap. This matches the legacy PIL pipeline.
            pixels = np.asarray(original).copy()

        if scale == 8:
            first = self._pass(pixels, 4, 0, 50, progress_callback, cancel_check)
            # Legacy pipeline wrote the 4x image as a PNG before the next pass.
            # An in-memory PNG roundtrip preserves uint8 samples and channel order.
            import io
            stream = io.BytesIO()
            Image.fromarray(first).save(stream, "PNG")
            stream.seek(0)
            with Image.open(stream) as stage:
                intermediate = np.asarray(stage).copy()
            output = self._pass(intermediate, 2, 50, 100, progress_callback, cancel_check)
        else:
            output = self._pass(pixels, scale, 0, 100, progress_callback, cancel_check)

        self._cancel_if_requested(cancel_check)
        result = Image.fromarray(output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        result.save(dest, format="PNG")
        return {"input": str(source), "output": str(dest),
                "input_size": original_size, "output_size": result.size,
                "scale": scale, "engine": "NiyomSilp Experimental Core"}
