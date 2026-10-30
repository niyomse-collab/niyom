"""V2.1 bounded contour regularization; no OCR, thresholding or glyph redraw."""
from __future__ import annotations

import cv2
import numpy as np

# Finite support: tensor window radius 24, tangent samples up to 6 pixels.
CONTOUR_HALO = 32


def _contour_delta_tile(rgb: np.ndarray, strength: float) -> np.ndarray:
    """Return colour corrections along coherent RGB edges, including isoluminant edges.

    A median along the contour rejects short edge excursions without averaging
    across the stroke. The RGB structure tensor gives an unsigned orientation;
    opposite edge signs no longer cancel as they did in the luminance average.
    Changes remain local (3px extrema) and bounded to 96 channel levels. This
    allows limited boundary movement, which a +/-15 colour clamp suppressed.
    """
    if strength <= 0 or min(rgb.shape[:2]) < 3:
        return np.zeros(rgb.shape, np.float32)
    base = rgb.astype(np.float32)
    gx = cv2.Sobel(base, cv2.CV_32F, 1, 0, ksize=3, scale=1/8)
    gy = cv2.Sobel(base, cv2.CV_32F, 0, 1, ksize=3, scale=1/8)

    def tensor(a):
        return cv2.GaussianBlur(a, (49, 49), 6.0)

    xx = tensor(np.sum(gx * gx, axis=2))
    yy = tensor(np.sum(gy * gy, axis=2))
    xy = tensor(np.sum(gx * gy, axis=2))
    coherence = np.sqrt((xx - yy)**2 + 4 * xy**2) / (xx + yy + 1e-5)
    angle = .5 * np.arctan2(2 * xy, xx - yy)
    nx, ny = np.cos(angle), np.sin(angle)
    y, x = np.indices(rgb.shape[:2], dtype=np.float32)
    samples = [base]
    for offset in (-6., -4., -2., 2., 4., 6.):
        samples.append(cv2.remap(base, x - offset * ny, y + offset * nx,
                                cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101))
    median = np.median(np.stack(samples), axis=0)
    gradient = np.sqrt(np.sum(gx * gx + gy * gy, axis=2))
    weight = np.clip((coherence - .2) / .5, 0, 1) * np.clip((gradient - 6) / 18, 0, 1)
    # Reject strongly textured photo areas. Selected face areas are restored
    # exactly by the caller, independently of this confidence estimate.
    denoised = cv2.bilateralFilter(rgb, 5, 24, 1.7)
    texture = cv2.GaussianBlur(np.mean(np.abs(base - denoised), axis=2), (17, 17), 2)
    weight *= np.clip((8 - texture) / 4, 0, 1)
    kernel = np.ones((7, 7), np.uint8)
    correction = np.clip(median - base, -96, 96)
    candidate = base + correction * weight[..., None] * np.sqrt(np.clip(strength, 0, 1))
    # Re-establish edge transition after tangential interpolation. Restrict to
    # the same graphic confidence and source neighbourhood extrema (no halo).
    edge_detail = candidate - cv2.GaussianBlur(candidate, (7, 7), .85)
    candidate += np.clip(edge_detail, -48, 48) * weight[..., None] * np.sqrt(np.clip(strength, 0, 1)) * 1.4
    candidate = np.clip(candidate, base - 96, base + 96)
    candidate = np.clip(candidate, cv2.erode(rgb, kernel), cv2.dilate(rgb, kernel))
    return candidate - base


def contour_delta(rgb: np.ndarray, strength: float) -> np.ndarray:
    """Bound temporary sample arrays independently of the print image size."""
    h, w = rgb.shape[:2]
    if max(h, w) <= 512:
        return _contour_delta_tile(rgb, strength)
    out = np.zeros(rgb.shape, np.float32)
    for y in range(0, h, 512):
        for x in range(0, w, 512):
            top, left = max(0, y - CONTOUR_HALO), max(0, x - CONTOUR_HALO)
            bottom, right = min(h, y + 512 + CONTOUR_HALO), min(w, x + 512 + CONTOUR_HALO)
            tile = _contour_delta_tile(rgb[top:bottom, left:right], strength)
            out[y:min(y+512,h), x:min(x+512,w)] = tile[y-top:min(y+512,h)-top, x-left:min(x+512,w)-left]
    return out
