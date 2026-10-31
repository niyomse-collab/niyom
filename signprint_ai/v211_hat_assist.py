"""Experimental additive HAT enhancement on top of the accepted V2 engine.

V2 Real-ESRGAN is always run first; HAT sees the exact same source.
Only bounded high-frequency luminance is transferred outside protected face
regions. The ordinary V2/GFPGAN face pipeline runs after this engine.
No pretrained weights are bundled or downloaded automatically.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image


def blend_v2_with_hat(v2_pixels, hat_pixels, strength=0.85, protected_regions=()):
    """Conservatively enrich V2 detail without replacing V2 colour or faces."""
    if (v2_pixels.shape != hat_pixels.shape or v2_pixels.ndim != 3
            or v2_pixels.shape[2] != 3 or v2_pixels.dtype != np.uint8
            or hat_pixels.dtype != np.uint8):
        raise ValueError("V2.1.1 HAT Assist requires matching uint8 RGB results")
    if not np.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("V2.1.1 HAT Assist strength must be between zero and one")
    if strength == 0:
        return v2_pixels.copy()

    base_luma = cv2.cvtColor(v2_pixels, cv2.COLOR_RGB2GRAY).astype(np.float32)
    hat_luma = cv2.cvtColor(hat_pixels, cv2.COLOR_RGB2GRAY).astype(np.float32)
    # No global HAT tones, tint, skin colour or colour balance is copied.
    base_detail = base_luma - cv2.GaussianBlur(base_luma, (0, 0), 1.35)
    hat_detail = hat_luma - cv2.GaussianBlur(hat_luma, (0, 0), 1.35)
    delta = np.clip(hat_detail - base_detail, -38.0, 38.0)
    gx = cv2.Sobel(base_luma, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(base_luma, cv2.CV_32F, 0, 1, ksize=3)
    # Apply only near an existing V2 edge. A flat region stays V2-identical.
    edge_weight = np.clip(cv2.magnitude(gx, gy) / 65.0, 0.0, 1.0)

    rgb = v2_pixels.astype(np.int16)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    skin = (r > 85) & (r > g + 12) & (g > b + 7) & (r > b + 27)
    weight = edge_weight * (~skin).astype(np.float32) * float(strength)
    h, w = base_luma.shape
    for rect in protected_regions or ():
        if len(rect) != 4 or not all(np.isfinite(v) for v in rect):
            raise ValueError("V2.1.1 HAT Assist: invalid protected face region")
        x1, y1, x2, y2 = rect
        if x2 <= x1 or y2 <= y1:
            continue
        margin = max(4, round(min((x2 - x1) * w, (y2 - y1) * h) * 0.15))
        left = max(0, int(np.floor(x1 * w)) - margin)
        top = max(0, int(np.floor(y1 * h)) - margin)
        right = min(w, int(np.ceil(x2 * w)) + margin)
        bottom = min(h, int(np.ceil(y2 * h)) + margin)
        weight[top:bottom, left:right] = 0

    # Add the *same* luminance detail to all RGB channels, but keep it
    # inside the gamut of every channel before addition. Naively clipping the
    # result to [0,255] would clip just red (or blue) on a saturated logo,
    # changing channel differences and washing out the V2 brand colour.
    base = v2_pixels.astype(np.float32)
    signed_detail = delta * weight
    available_up = 255.0 - np.max(base, axis=2)
    available_down = np.min(base, axis=2)
    signed_detail = np.maximum(
        -available_down, np.minimum(signed_detail, available_up)
    )
    output = np.rint(base + signed_detail[..., None]).astype(np.uint8)
    return output


class HATAssistEngine:
    """V2 engine plus HAT, preserving the existing .enhance/.enhance_tile API."""

    def __init__(self, v2_engine, hat_engine, strength=0.85, protected_regions=()):
        self.v2 = v2_engine
        self.hat = hat_engine
        self.strength = strength
        self.protected_regions = protected_regions
        # HAT needs smaller inference tiles than V2's Real-ESRGAN 256 tile.
        self.upsampler = SimpleNamespace(
            tile_size=min(v2_engine.upsampler.tile_size or 256,
                          hat_engine.upsampler.tile_size or 96),
            tile_pad=max(v2_engine.upsampler.tile_pad, hat_engine.upsampler.tile_pad),
        )

    def device_name(self):
        return self.v2.device_name()

    def enhance_graphic_tile(self, pixels, scale, cancel, protected_regions=()):
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")
        if hasattr(self.v2, "enhance_graphic_tile"):
            base = self.v2.enhance_graphic_tile(pixels, scale, cancel, protected_regions)
        else:
            base = self.v2.enhance_tile(pixels, scale, cancel)
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")
        assist = self.hat.enhance_tile(pixels, scale, cancel)
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")
        return blend_v2_with_hat(base, assist, self.strength, protected_regions)

    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        return self.enhance_graphic_tile(
            pixels, scale, cancel_check, self.protected_regions
        )

    def enhance(self, src, dst, scale=4, progress_callback=None, cancel_check=None):
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        with TemporaryDirectory(prefix="niyomsil_v211_hat_assist_") as directory:
            base_path = Path(directory) / "v2.png"
            hat_path = Path(directory) / "hat.png"
            def v2_progress(value):
                if progress_callback:
                    progress_callback(round(max(0, min(100, value)) * 0.6))
            def hat_progress(value):
                if progress_callback:
                    progress_callback(60 + round(max(0, min(100, value)) * 0.4))
            result = self.v2.enhance(
                src, base_path, scale, v2_progress, cancel_check
            )
            if cancel_check and cancel_check():
                raise InterruptedError("Processing stopped by user")
            self.hat.enhance(src, hat_path, scale, hat_progress, cancel_check)
            if cancel_check and cancel_check():
                raise InterruptedError("Processing stopped by user")
            with Image.open(base_path) as base_image, Image.open(hat_path) as hat_image:
                base = np.asarray(base_image.convert("RGB"))
                assist = np.asarray(hat_image.convert("RGB"))
            output = blend_v2_with_hat(base, assist, self.strength, self.protected_regions)
            destination = Path(dst)
            destination.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(output, "RGB").save(destination)
            return {**(result or {}), "model": "V2 RealESRGAN + HAT Assist",
                    "hat_assist": True, "output_size": (output.shape[1], output.shape[0])}
