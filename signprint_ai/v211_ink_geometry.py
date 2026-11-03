"""Experimental geometric recovery of blurred FLAT graphic ink over accepted V2.

This is a *local subpixel colour-coverage* reconstruction, not generative
redrawing/OCR. It cannot recover an illegible letter's spelling. The module is
research-only and OFF until real V2 A/B plus Thai glyph/print tests pass.

Only scenes dominated by flat two-colour material are eligible. Photographs,
selected faces and all non-opaque cutout edges are kept unchanged. Bounded
sample radius (3 pixels) and output clipped to local source extrema prevent
glowing halos and invented colours. 8x / disk tile seams still need production
QA before enabling.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image


def reconstruct_ink_pixels(rgb: np.ndarray, *, strength: float = 1.0,
                           protected_regions=(), alpha: np.ndarray | None = None):
    """Return (RGB, audit) without resizing, hallucinating glyphs, or touching alpha.

    Color samples on opposite sides of the locally coherent edge estimate a
    two-colour anti-alias coverage. Smoothstep steepens blurred coverage while
    preserving the estimated edge centre and both original ink colours.
    """
    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
            or rgb.ndim != 3 or rgb.shape[2] != 3):
        raise ValueError("Ink geometry requires uint8 RGB")
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Ink geometry strength must be finite 0..1")
    height, width = rgb.shape[:2]
    result = rgb.copy()
    audit = {"eligible": False, "changed_pixels_pct": 0.0,
             "reason": "unchanged", "quality_certified": False}
    if not strength or min(height, width) < 64:
        audit["reason"] = "disabled_or_too_small"
        return result, audit
    if alpha is not None:
        if (alpha.dtype != np.uint8 or alpha.shape != (height, width)):
            raise ValueError("Ink geometry alpha shape/type mismatch")

    base = rgb.astype(np.float32)
    nearby = cv2.GaussianBlur(base, (0, 0), 1.0)
    local_std = np.sqrt(np.maximum(
        cv2.GaussianBlur(base * base, (0, 0), 1.0) - nearby * nearby, 0
    ).mean(axis=2))
    # An unblurred face/photograph has large mid-frequency density. This
    # conservative global/ROI gate avoids turning realistic textures into
    # posterized "AI" ink. False negatives preserve approved V2 output.
    flat_fraction = float(np.mean(local_std < 6))
    audit["flat_fraction"] = round(flat_fraction, 5)
    if flat_fraction < .76:
        audit["reason"] = "photographic_texture_keep_v2"
        return result, audit

    guide = cv2.GaussianBlur(base, (0, 0), .45)
    gx = cv2.Sobel(guide, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(guide, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    xx = cv2.GaussianBlur(np.sum(gx * gx, axis=2), (0, 0), 1.2)
    yy = cv2.GaussianBlur(np.sum(gy * gy, axis=2), (0, 0), 1.2)
    xy = cv2.GaussianBlur(np.sum(gx * gy, axis=2), (0, 0), 1.2)
    coherence = np.sqrt((xx-yy)**2 + 4*xy*xy) / (xx+yy+1e-4)
    theta = .5 * np.arctan2(2*xy, xx-yy)
    nx, ny = np.cos(theta), np.sin(theta)
    y, x = np.indices((height, width), dtype=np.float32)
    radius = 3.0

    def sample(pixels, sign):
        return cv2.remap(
            pixels, x+sign*radius*nx, y+sign*radius*ny,
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
        )

    side_a, side_b = sample(base, -1), sample(base, 1)
    delta = side_b - side_a
    d2 = np.sum(delta * delta, axis=2) + 1e-4
    distance = np.sqrt(d2)
    cover = np.clip(np.sum((base-side_a)*delta, axis=2)/d2, 0, 1)
    projected = side_a + cover[..., None]*delta
    off_palette = np.mean(np.abs(projected-base), axis=2)

    # Three rounds of monotone coverage sharpening; no thresholds or stroke
    # erosion, so narrow Thai tone marks cannot be deliberately removed.
    sharp_cover = cover.copy()
    for _ in range(3):
        sharp_cover = sharp_cover*sharp_cover*(3-2*sharp_cover)
    target = side_a + sharp_cover[..., None]*delta

    source_gx = cv2.Sobel(base, cv2.CV_32F, 1, 0, ksize=3)
    source_gy = cv2.Sobel(base, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.sqrt(np.sum(source_gx**2 + source_gy**2, axis=2))
    edge_weight = np.clip((gradient-100)/300, 0, 1)
    anchor_std = np.maximum(sample(local_std, -1), sample(local_std, 1))
    anchor_confidence = np.clip((28-anchor_std)/19, 0, 1)
    weight = (
        np.clip((distance-60)/100, 0, 1)
        * np.clip((coherence-.70)/.2, 0, 1)
        * np.clip((12-off_palette)/8, 0, 1)
        * edge_weight * anchor_confidence * strength
    )
    if alpha is not None:
        safe = cv2.erode((alpha == 255).astype(np.uint8),
                         np.ones((9, 9), np.uint8)) != 0
        weight[~safe] = 0
    for region in protected_regions or ():
        if len(region) != 4 or not all(math.isfinite(float(v)) for v in region):
            raise ValueError("Protected face ROI must be four finite coordinates")
        x1, y1, x2, y2 = map(float, region)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Protected face ROI must be normalized 0..1")
        margin = max(8, round(min((x2-x1)*width,
                                  (y2-y1)*height)*.15))
        left = max(0, math.floor(x1*width)-margin)
        top = max(0, math.floor(y1*height)-margin)
        right = min(width, math.ceil(x2*width)+margin)
        bottom = min(height, math.ceil(y2*height)+margin)
        weight[top:bottom, left:right] = 0

    candidate = base + (target-base)*weight[..., None]
    # Never invent coloured ringing beyond nearby ink and paper extrema.
    lower = cv2.erode(rgb, np.ones((7, 7), np.uint8)).astype(np.float32)
    upper = cv2.dilate(rgb, np.ones((7, 7), np.uint8)).astype(np.float32)
    candidate = np.maximum(lower, np.minimum(upper, candidate))
    result = np.rint(np.clip(candidate, 0, 255)).astype(np.uint8)
    audit["eligible"] = True
    audit["reason"] = "flat_graphic_coverage_reconstructed"
    audit["changed_pixels_pct"] = round(float(
        np.mean(np.max(np.abs(result.astype(np.int16)
                           - rgb.astype(np.int16)), axis=2) > 3)*100
    ), 4)
    return result, audit


def finish_flat_ink_geometry(image: Image.Image, *, strength: float = 1.0,
                             protected_regions=()):
    """Pillow adapter: same dimensions, same alpha and transparent background."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    alpha = (np.asarray(image.getchannel("A"), dtype=np.uint8)
             if "A" in image.getbands() else None)
    result, audit = reconstruct_ink_pixels(
        rgb, strength=strength, protected_regions=protected_regions,
        alpha=alpha
    )
    out = Image.fromarray(result, "RGB")
    if alpha is not None:
        out.putalpha(Image.fromarray(alpha, "L"))
    return out, audit
