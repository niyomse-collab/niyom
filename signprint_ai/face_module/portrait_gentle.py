"""Independent, optional gentle retouch of a selected 512px portrait crop.

This code does not implement or modify Real-ESRGAN, GFPGAN, or Photoshop.
It accepts GFPGAN's candidate crop and the *existing* ARM crop and produces a
conservative, identity-preserving candidate for a user-selected face only.
No external models, Photoshop extension scripts, downloads, or side effects.
"""

from __future__ import annotations

import cv2
import numpy as np


def gentle_blend_face(
    original_bgr: np.ndarray,
    restored_bgr: np.ndarray,
    *,
    alpha: float = 0.45,
) -> np.ndarray:
    """Blend a candidate face conservatively; do not alter the caller's arrays.

    A 5x5 Canny/dilated edge mask protects existing facial lines. Pixels whose
    proposed color change is unusually large are also given lower weight.
    Low-gradient areas get a *small*, edge-aware bilateral cleanup to reduce
    chroma speckling without flattening details. This is not an identity
    verification system: a human must still review actual faces at 100% zoom.

    The function operates only on an already-aligned *face crop*, never the
    full signage image. The default production path must not call it.
    """
    if (
        not isinstance(original_bgr, np.ndarray)
        or not isinstance(restored_bgr, np.ndarray)
        or original_bgr.dtype != np.uint8
        or restored_bgr.dtype != np.uint8
        or original_bgr.ndim != 3
        or original_bgr.shape[2] != 3
        or original_bgr.shape != restored_bgr.shape
    ):
        raise ValueError("Expected equally sized uint8 BGR face crops (H,W,3)")
    if not np.isfinite(alpha):
        raise ValueError("Blend strength must be finite")

    strength = float(np.clip(alpha, 0.0, 0.55))
    if strength == 0.0 or np.array_equal(original_bgr, restored_bgr):
        return original_bgr.copy()

    gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
    line_mask = cv2.Canny(gray, 55, 110)
    line_mask = cv2.dilate(
        line_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    )
    line_mask = cv2.GaussianBlur(
        line_mask.astype(np.float32) / 255.0, (0, 0), 2.0
    )

    src = original_bgr.astype(np.float32)
    proposed = restored_bgr.astype(np.float32)
    difference = np.mean(np.abs(proposed - src), axis=2)
    # Reduce extreme changes such as invented teeth/lip colors. Avoid an
    # absolute rejection on blurry faces: moderate restoration remains possible.
    drift_mask = np.clip((difference - 32.0) / 72.0, 0.0, 1.0)
    per_pixel_weight = (
        strength * (1.0 - 0.72 * line_mask) * (1.0 - 0.70 * drift_mask)
    )
    mixed = src + (proposed - src) * per_pixel_weight[..., None]
    mixed = np.clip(np.rint(mixed), 0, 255).astype(np.uint8)

    # Very mild chroma/color speckle reduction in flat regions only. Preserve
    # all high-contrast lines; do not run global skin blur.
    smoothed = cv2.bilateralFilter(
        mixed, d=5, sigmaColor=18.0, sigmaSpace=2.2
    )
    cleanup_weight = 0.12 * strength * (1.0 - line_mask)
    result = (
        mixed.astype(np.float32) * (1.0 - cleanup_weight[..., None])
        + smoothed.astype(np.float32) * cleanup_weight[..., None]
    )
    return np.clip(np.rint(result), 0, 255).astype(np.uint8)
