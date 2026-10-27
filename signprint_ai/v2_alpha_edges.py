"""Alpha-aware V2 preparation for transparent PNG cutouts.

AI upsampling interpolates RGB without alpha awareness. PNGs generated with
black/white RGB in fully transparent pixels can therefore acquire a visible
fringe at their semi-transparent edge after model inference. Replace ONLY RGB
in zero-alpha pixels near visible artwork; alpha and visible RGB are untouched.
This does not vectorize or invent detail, and does not run on opaque sources.
"""
from __future__ import annotations

import cv2
import numpy as np


def bleed_transparent_rgb(rgb: np.ndarray, alpha: np.ndarray, radius: int = 5) -> np.ndarray:
    if (rgb.ndim != 3 or rgb.shape[2] != 3 or alpha.shape != rgb.shape[:2]
            or rgb.dtype != np.uint8 or alpha.dtype != np.uint8):
        raise ValueError("Expected RGB uint8 with matching alpha uint8")
    # The zero-alpha RGB never appears directly, but AI can mix it into visible
    # pixels. Limit inpainting to a small margin outside existing artwork.
    invisible = (alpha == 0)
    visible = (alpha > 0)
    if not invisible.any() or not visible.any():
        return rgb.copy()
    near_visible = cv2.dilate(
        visible.astype(np.uint8), np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8)
    ).astype(bool)
    masked = (invisible & near_visible).astype(np.uint8) * 255
    if not masked.any():
        return rgb.copy()
    # Inpainting never changes any pixel where alpha > 0.
    return cv2.inpaint(rgb, masked, min(radius, 5), cv2.INPAINT_TELEA)
