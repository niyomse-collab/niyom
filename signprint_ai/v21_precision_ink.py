"""V2.1 precision-ink finishing: additional edge-aware cleanup over accepted V2.

No OCR, recolouring of entire masks, or new AI-detail hallucinations. The V2
model output and original V2 finishing are preserved as the input to this
optional stage. It is not a replacement for the Real-ESRGAN neural model.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image



def photo_preservation_weight(rgb: np.ndarray, gx: np.ndarray,
                              gy: np.ndarray, gradient: np.ndarray) -> np.ndarray:
    """Reduce finishing on photographic texture / skin, retaining coherent ink.

    Pure 31x31 edge exclusion removes the entire interior of narrow Thai
    strokes; instead use directional coherence to keep long graphic strokes
    while suppressing dense, multidirectional photographic details.

    All operators are translation-invariant with finite (<=32 px) context
    so V2.1 disk-tiled exports match the in-memory finishing near tile seams.
    """
    # A local average gradient distinguishes dense food/photographic texture
    # from smooth graphic ink. Parallel letter strokes have strong coherence,
    # so they are not excluded solely for having nearby outlines.
    regional_gradient = cv2.GaussianBlur(gradient, (0, 0), 6.0)
    texture_confidence = np.clip(
        (85.0 - regional_gradient) / 55.0, 0.0, 1.0
    )
    gx2 = cv2.GaussianBlur(np.sum(gx * gx, axis=2), (0, 0), 6.0)
    gy2 = cv2.GaussianBlur(np.sum(gy * gy, axis=2), (0, 0), 6.0)
    gxy = cv2.GaussianBlur(np.sum(gx * gy, axis=2), (0, 0), 6.0)
    coherence = np.sqrt((gx2 - gy2) ** 2 + 4 * gxy ** 2) / (
        gx2 + gy2 + 1e-4
    )
    coherent_stroke = np.clip((coherence - .60) / .30, 0, 1)
    texture_confidence = np.maximum(texture_confidence, coherent_stroke)

    # Suppress unwarranted skin retouching even when Face Protect was not
    # selected. Require a reddish skin-like chroma *and* a meaningful R-G
    # separation: pale cream sign backgrounds must NOT be mistaken for skin.
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    cr, cb = ycrcb[..., 1], ycrcb[..., 2]
    red, green, blue = (
        rgb[..., 0].astype(np.int16),
        rgb[..., 1].astype(np.int16),
        rgb[..., 2].astype(np.int16),
    )
    saturation = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 1]
    skin_like = (
        (cr >= 135) & (cr <= 180) & (cb >= 80) & (cb <= 140)
        & (red > green) & (green > blue)
        & (red - green > 22) & (green < 215)
        & (red > 90) & (saturation < 125)
    )
    skin_presence = cv2.GaussianBlur(
        skin_like.astype(np.float32), (0, 0), 6.0
    )
    skin_confidence = np.clip(
        (.24 - skin_presence) / .16, 0.0, 1.0
    )
    return (texture_confidence * skin_confidence).astype(np.float32)

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
    # Old V2.1+ at slider 100 also smoothed face/food photographic texture.
    # Protect those regions; keep coherent narrow Thai ink strokes eligible.
    weight *= photo_preservation_weight(rgb, gx, gy, grad)
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
