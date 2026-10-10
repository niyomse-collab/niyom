"""Niyom-owned conservative portrait processing; no generative face replacement.

AI inference is injected by the host. Without it, resize is explicitly labelled
interpolation, never AI restoration. RGB uint8 arrays are used throughout.
"""
from dataclasses import dataclass
from typing import Callable
import cv2
import numpy as np


@dataclass(frozen=True)
class PortraitSettings:
    scale: int = 2
    denoise: float = 0.5
    detail: float = 0.25
    ai_blend: float = 0.35
    tile: int = 256
    max_pixels: int = 80_000_000

    def validate(self):
        if self.scale not in (1, 2, 4):
            raise ValueError('Portrait scale must be 1, 2 or 4')
        for value in (self.denoise, self.detail, self.ai_blend):
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Portrait strengths must be between 0 and 1')
        if self.tile < 32 or self.max_pixels < 1:
            raise ValueError('Invalid portrait memory limits')


def process_portrait(rgb: np.ndarray, settings: PortraitSettings = PortraitSettings(),
                     upscale: Callable | None = None, progress=None, cancel=None):
    """Return (RGB, metadata). upscale(rgb, scale, cancel) must return RGB uint8.

    Denoising tiles use context halos and disjoint writes. A bounded AI residual
    limits colour drift; it cannot guarantee identity preservation. The caller
    must present a before/after preview for approval of severe degradation.
    """
    settings.validate()
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
        raise ValueError('Expected nonempty RGB uint8 image')
    h, w = rgb.shape[:2]
    if h * w * settings.scale ** 2 > settings.max_pixels:
        raise ValueError('Portrait output exceeds memory budget; reduce scale')

    def check():
        if cancel and cancel():
            raise InterruptedError('Portrait processing cancelled')

    def notify(value, label):
        check()
        if progress:
            progress(value, label)

    clean = rgb.copy()
    tile = settings.tile
    total = ((h + tile - 1) // tile) * ((w + tile - 1) // tile)
    done = 0
    # NLM search radius 10 plus template radius 3: 16px context is sufficient.
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            check()
            y1, x1 = min(h, y + tile), min(w, x + tile)
            ya, xa = max(0, y - 16), max(0, x - 16)
            patch = rgb[ya:min(h, y1 + 16), xa:min(w, x1 + 16)]
            if settings.denoise:
                patch = cv2.fastNlMeansDenoisingColored(
                    patch, None, 2 + 7 * settings.denoise,
                    3 + 9 * settings.denoise, 7, 21)
            clean[y:y1, x:x1] = patch[y-ya:y1-ya, x-xa:x1-xa]
            done += 1
            notify(round(40 * done / total), 'Portrait · ลดนอยส์จากต้นฉบับ')
    size = (w * settings.scale, h * settings.scale)
    baseline = cv2.resize(clean, size, interpolation=cv2.INTER_CUBIC)
    notify(42, 'Portrait · ขยายภาพ')
    ai_used = upscale is not None and settings.scale > 1 and settings.ai_blend > 0
    if ai_used:
        candidate = upscale(clean.copy(), settings.scale, cancel)
        check()
        if candidate.dtype != np.uint8 or candidate.shape != baseline.shape:
            raise ValueError('AI backend returned invalid RGB dimensions or dtype')
    else:
        candidate = baseline
    # Work in strips to bound temporary memory on large print images.
    out = np.empty_like(baseline)
    for y in range(0, size[1], tile):
        check()
        end = min(size[1], y + tile)
        ya, yb = max(0, y - 8), min(size[1], end + 8)
        base = baseline[ya:yb].astype(np.float32)
        residual = candidate[ya:yb].astype(np.float32) - base
        mixed = base + np.clip(residual, -18, 18) * settings.ai_blend
        lum = cv2.cvtColor(np.clip(mixed, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        edges = np.maximum(np.abs(cv2.Sobel(lum, cv2.CV_32F, 1, 0)),
                           np.abs(cv2.Sobel(lum, cv2.CV_32F, 0, 1)))
        detail = mixed - cv2.GaussianBlur(mixed, (0, 0), 0.8)
        detail[np.abs(detail) < 3] = 0
        gain = np.clip(edges / 80, 0, 1)[..., None] * settings.detail
        finished = mixed + np.clip(detail, -5, 5) * gain
        out[y:end] = np.clip(np.rint(finished[y-ya:end-ya]), 0, 255).astype(np.uint8)
        notify(80 + round(20 * end / size[1]), 'Portrait · รักษาผิวและเพิ่มรายละเอียด')
    return out, {'mode': 'studio', 'ai_used': ai_used,
                 'scale': settings.scale, 'face_replacement': False,
                 'identity_guaranteed': False}
