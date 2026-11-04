"""Conservative automatic lettering/graphic edge cleanup for v2 only.

Works on RGB pixels, never changes glyph topology or the alpha channel.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def refine_sign_edges(image: Image.Image) -> Image.Image:
    """Reduce color fringe around high-contrast, locally flat graphics.

    Only high-contrast edges adjacent to nearly uniform colors are refined.
    Avoid aggressive morphological operations that could break Thai marks.
    """
    if image.width < 64 or image.height < 64:
        return image
    original_mode = image.mode
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    # Flat neighborhoods are common in text and logos, unlike photographs.
    local_mean = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), 2.0)
    variance = cv2.GaussianBlur(
        (rgb.astype(np.float32) - local_mean) ** 2, (0, 0), 1.0
    ).mean(axis=2)
    mask = ((gradient > 75) & (variance < 2800)).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (0, 0), 0.6) * 0.35
    if not np.any(mask):
        return image.copy()
    # Small, bounded luminance-only enhancement prevents colored halos.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    light = lab[..., 0].astype(np.float32)
    blur = cv2.GaussianBlur(light, (0, 0), 0.8)
    correction = np.clip(light - blur, -8.0, 8.0) * mask
    lab[..., 0] = np.clip(light + correction, 0, 255).astype(np.uint8)
    result = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), "RGB")
    if original_mode == "RGBA" or "A" in image.getbands():
        result.putalpha(image.getchannel("A"))
    return result
