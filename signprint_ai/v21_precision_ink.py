"""V2.1 precision-ink finishing: additional edge-aware cleanup over accepted V2.

No OCR, recolouring of entire masks, or new AI-detail hallucinations. The V2
model output and original V2 finishing are preserved as the input to this
optional stage. It is not a replacement for the Real-ESRGAN neural model.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def precision_ink_finish(image: Image.Image, settings, protected_regions=None) -> Image.Image:
    """Stabilize tiny ink speckles without crossing strong colour outlines."""
    flat = float(np.clip(getattr(settings, "flat_smoothing", 0), 0, 100)) / 100.0
    denoise = float(np.clip(getattr(settings, "denoise", 0), 0, 100)) / 100.0
    text = float(np.clip(getattr(settings, "text_graphic_boost", 0), 0, 100)) / 100.0
    sharpen = float(np.clip(getattr(settings, "sharpness", 0), 0, 100)) / 100.0
    if max(flat, denoise, text, sharpen) <= 0 or min(image.size) < 64:
        return image.copy()

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    base = rgb.astype(np.float32)
    guide = cv2.bilateralFilter(rgb, 5, 30, 1.6)
    gx = cv2.Sobel(guide, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(guide, cv2.CV_32F, 0, 1, ksize=3)
    # Channel-aware edges also cover red/green isoluminant lettering.
    grad = np.maximum(np.abs(gx).max(axis=2), np.abs(gy).max(axis=2))
    kernel = np.ones((3, 3), np.uint8)
    span = (
        cv2.dilate(rgb, kernel).astype(np.int16)
        - cv2.erode(rgb, kernel).astype(np.int16)
    ).max(axis=2)
    confidence = np.clip((125.0 - grad) / 75.0, 0.0, 1.0)
    confidence *= np.clip((85.0 - span) / 50.0, 0.0, 1.0)
    confidence = cv2.GaussianBlur(confidence.astype(np.float32), (3, 3), .65)

    # Multiple colour-guided passes at strong slider levels; high contrast
    # lettering edges do not get averaged with the differently coloured paper.
    stable = cv2.bilateralFilter(rgb, 9, 55, 3.5)
    if flat > .30:
        stable = cv2.bilateralFilter(stable, 9, 45, 3.5)
    if flat > .70:
        stable = cv2.bilateralFilter(stable, 13, 45, 5.0)
    if denoise:
        noise_ref = cv2.bilateralFilter(rgb, 5, 36, 2.0)
        stable = np.clip(
            stable.astype(np.float32) * (1 - denoise*.25)
            + noise_ref.astype(np.float32) * denoise*.25,
            0, 255,
        ).astype(np.uint8)
    weight = np.clip((flat*.95 + denoise*.20) * confidence, 0.0, 1.0)
    result_f = (
        base * (1.0 - weight[..., None])
        + stable.astype(np.float32) * weight[..., None]
    )

    # Extra bounded detail on selected coherent edges. Unlike unrestricted
    # unsharp-mask this never creates channel values outside local source ink
    # extrema, preventing new bright/dark halos around coloured glyphs.
    if text or sharpen:
        high = base - cv2.GaussianBlur(base, (0, 0), .75)
        edge_conf = np.clip((grad - 50.0) / 125.0, 0.0, 1.0)
        gain = text*.22 + sharpen*.16
        result_f += np.clip(high*gain, -10.0, 10.0) * edge_conf[..., None]
        minimum = cv2.erode(rgb, kernel).astype(np.float32)
        maximum = cv2.dilate(rgb, kernel).astype(np.float32)
        result_f = np.clip(result_f, minimum, maximum)
    result = np.rint(result_f).clip(0, 255).astype(np.uint8)

    # Preserve cutout alpha exactly and never edit hidden/partial RGB along
    # alpha boundaries; these values otherwise produce black CMYK fringes.
    if "A" in image.getbands():
        alpha = np.asarray(image.getchannel("A"))
        safe = cv2.erode(
            (alpha == 255).astype(np.uint8), np.ones((5, 5), np.uint8)
        ) != 0
        result[~safe] = rgb[~safe]

    if protected_regions:
        h, w = rgb.shape[:2]
        for x1, y1, x2, y2 in protected_regions:
            if not all(np.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            margin = max(8, round(min((x2-x1)*w, (y2-y1)*h)*.12))
            left = max(0, int(np.floor(x1*w))-margin)
            top = max(0, int(np.floor(y1*h))-margin)
            right = min(w, int(np.ceil(x2*w))+margin)
            bottom = min(h, int(np.ceil(y2*h))+margin)
            result[top:bottom, left:right] = rgb[top:bottom, left:right]

    output = Image.fromarray(result, "RGB")
    if "A" in image.getbands():
        output.putalpha(image.getchannel("A"))
    return output
