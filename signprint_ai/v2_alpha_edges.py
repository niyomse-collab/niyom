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
    # Composite-safe RGB propagation: normalise a blurred foreground-only
    # colour field by its blurred opacity weight. Unlike inpainting a narrow
    # ring, this never samples black hidden RGB outside the inpaint mask.
    invisible = alpha == 0
    visible = alpha > 0
    if not invisible.any() or not visible.any():
        return rgb.copy()
    near_visible = cv2.dilate(
        visible.astype(np.uint8),
        np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8),
    ) > 0
    repair = invisible & near_visible
    if not repair.any():
        return rgb.copy()
    weights = (alpha.astype(np.float32) / 255.0) ** 2
    sigma = max(1.0, radius * 0.8)
    denom = cv2.GaussianBlur(weights, (0, 0), sigma)
    filled = rgb.copy()
    suitable = repair & (denom > 1e-5)
    for c in range(3):
        numerator = cv2.GaussianBlur(
            rgb[..., c].astype(np.float32) * weights, (0, 0), sigma
        )
        estimate = np.clip(numerator / np.maximum(denom, 1e-5), 0, 255).astype(np.uint8)
        filled[..., c][suitable] = estimate[suitable]
    return filled
