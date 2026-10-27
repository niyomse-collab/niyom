"""Selective, automatic lettering and flat-colour graphic cleanup for v2.

This is not OCR or vector tracing. It only changes high-confidence contours
and nearby nearly-flat fills, without changing pixel alpha or glyph topology.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def refine_sign_edges(
    image: Image.Image,
    protected_regions: tuple[tuple[float, float, float, float], ...] | None = None,
    *, settings=None,
) -> Image.Image:
    """Keep lettering contours crisp without reprocessing selected face ROIs.

    Protected rectangles are normalized (x1, y1, x2, y2) within *this image*.
    No thresholding or erosion of rendered text shapes occurs; tiny Thai vowels
    and tone marks are retained, as is the exact source alpha plane.
    """
    # None retains the standalone refinement API; V2 always passes UI settings.
    def strength(name):
        return float(np.clip(getattr(settings, name, 0), 0, 100)) / 100.0

    if settings is not None and not any(strength(k) for k in
            ("denoise", "flat_smoothing", "text_graphic_boost", "sharpness",
             "contrast") + (("saturation",) if getattr(settings, "saturation", 0) else ())):
        return image.copy()
    if image.width < 64 or image.height < 64:
        return image.copy()

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    # Bilateral filtering smooths mild colour noise without mixing both sides
    # of a strong lettering edge, unlike an unrestricted Gaussian blur.
    denoised = cv2.bilateralFilter(rgb, 5, 24, 1.7)
    gray = cv2.cvtColor(denoised, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    local_gradient = cv2.GaussianBlur(gradient, (0, 0), 1.8)
    direction_x = cv2.GaussianBlur(gx, (0, 0), 1.8)
    direction_y = cv2.GaussianBlur(gy, (0, 0), 1.8)
    coherence = cv2.magnitude(direction_x, direction_y) / (local_gradient + 1e-3)
    color_noise = np.mean(
        np.abs(rgb.astype(np.float32) - denoised.astype(np.float32)), axis=2
    )
    texture = cv2.GaussianBlur(color_noise, (0, 0), 2.0)

    # High-contrast, locally coherent edges with nearby solid colours are
    # more likely text/graphic strokes than highly textured photographs.
    contours = (gradient > 95) & (coherence > 0.65) & (texture < 4.5)
    edge_weight = cv2.GaussianBlur(contours.astype(np.float32), (0, 0), 0.65)
    edge_weight *= np.clip((gradient - 35.0) / 115.0, 0.0, 1.0) * 0.9

    # Lightness-only edge correction avoids coloured fringes at blue/red/gold
    # text borders. The amplitude is bounded below after both passes.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    light = lab[..., 0].astype(np.float32)
    lowpass = cv2.GaussianBlur(light, (0, 0), 0.85)
    correction = np.clip(light - lowpass, -17.0, 17.0) * edge_weight
    lab[..., 0] = np.rint(np.clip(light + correction, 0, 255)).astype(np.uint8)
    sharpened = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    sharpened[edge_weight < 0.001] = rgb[edge_weight < 0.001]

    # Fill tiny speckles only inside low-gradient areas next to trustworthy
    # contours. Never smooth through the actual glyph boundary.
    vicinity = cv2.dilate(
        contours.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)),
    ) > 0
    filled = (gradient < 23) & (texture < 5) & vicinity
    blended = np.rint(
        rgb.astype(np.float32) * 0.2 + denoised.astype(np.float32) * 0.8
    ).astype(np.uint8)
    sharpened[filled] = blended[filled]

    # Do not invent new channel extrema (halos) or radically recolour strokes.
    minimum = cv2.erode(rgb, np.ones((3, 3), np.uint8)).astype(np.int16)
    maximum = cv2.dilate(rgb, np.ones((3, 3), np.uint8)).astype(np.int16)
    original = rgb.astype(np.int16)
    sharpened = np.clip(
        sharpened.astype(np.int16),
        np.maximum(minimum, original - 15),
        np.minimum(maximum, original + 15),
    ).astype(np.uint8)

    if settings is not None:
        base = rgb.astype(np.float32)
        text = strength("text_graphic_boost")
        # Blend the existing contour/fill correction with a true zero bypass.
        adjusted = base + (sharpened.astype(np.float32) - base) * text
        flat_weight = np.clip(1.0 - gradient / 55.0, 0, 1)[..., None]
        adjusted += (denoised.astype(np.float32) - base) * strength("denoise") * flat_weight
        # A larger but *region-gated* flat-colour correction removes mild
        # low-frequency waviness, not photographic texture or intentional
        # highlights. Keep a wide distance from text/graphic boundaries so the
        # large smoothing kernel cannot bleed background into lettering.
        flat = strength("flat_smoothing")
        if flat:
            barrier = cv2.dilate(
                (gradient > 30).astype(np.uint8), np.ones((31, 31), np.uint8)
            ) != 0
            local_kernel = np.ones((13, 13), np.uint8)
            colour_span = (
                cv2.dilate(rgb, local_kernel).astype(np.int16)
                - cv2.erode(rgb, local_kernel).astype(np.int16)
            ).max(axis=2)
            safe_flat = (~barrier) & (colour_span <= 22)
            flat_reference = cv2.GaussianBlur(base, (0, 0), 6.0)
            adjusted += (flat_reference - base) * flat * 0.90 * safe_flat[..., None]

        # Along-contour averaging gently settles single-pixel zigzags on
        # locally coherent curves/straight strokes, without blurring across
        # the stroke. This is not vector reconstruction or OCR.
        if text:
            tangential_norm = cv2.magnitude(direction_x, direction_y) + 1e-3
            tangent_x = -direction_y / tangential_norm
            tangent_y = direction_x / tangential_norm
            grid_y, grid_x = np.indices(gray.shape, dtype=np.float32)
            along = np.zeros_like(base)
            for offset in (-3.0, 3.0):
                along += cv2.remap(
                    base,
                    grid_x + offset * tangent_x,
                    grid_y + offset * tangent_y,
                    interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT_101,
                )
            along *= 0.5
            # Give the tangent estimate priority over local sharpening at
            # high-confidence edges; otherwise sharpening cancels smoothing.
            adjusted += (along - adjusted) * text * np.minimum(
                edge_weight * 1.3, 0.9
            )[..., None]

        detail = base - cv2.GaussianBlur(base, (0, 0), 0.85)
        detail[np.abs(detail) < 2.0] = 0
        adjusted += np.clip(detail, -17, 17) * edge_weight[..., None] * strength("sharpness")
        # Local contrast changes only trustworthy contour luminance. Avoid
        # CLAHE blocks on print flat fills and preserve intentional shadows.
        local_contrast = strength("contrast")
        if local_contrast:
            local_light = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
            local_background = cv2.GaussianBlur(local_light, (0, 0), 2.2)
            change = np.clip(local_light - local_background, -15, 15)
            adjusted += change[..., None] * edge_weight[..., None] * local_contrast * 0.42

        # Saturation slider accepts -30..30. The zero position is an exact
        # bypass, and the global channel +/-15 clamp still limits changes.
        sat = float(np.clip(getattr(settings, "saturation", 0), -30, 30))
        if sat:
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
            hsv[..., 1] = np.clip(hsv[..., 1] * (1 + sat / 100.0 * 0.55), 0, 255)
            saturated = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
            adjusted += (saturated.astype(np.float32) - base)

        sharpened = np.rint(np.clip(adjusted,
            np.maximum(minimum, original - 15),
            np.minimum(maximum, original + 15))).astype(np.uint8)
        # Hidden RGB must not bleed into partially transparent cutout borders.
        if "A" in image.getbands():
            opaque = np.asarray(image.getchannel("A")) == 255
            safe = cv2.erode(opaque.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
            sharpened[~safe] = rgb[~safe]

    if protected_regions:
        h, w = rgb.shape[:2]
        for x1, y1, x2, y2 in protected_regions:
            if not all(np.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            # Restore original face and an additional safety margin exactly.
            margin = max(8, round(min((x2 - x1) * w, (y2 - y1) * h) * 0.12))
            left = max(0, int(np.floor(x1 * w)) - margin)
            top = max(0, int(np.floor(y1 * h)) - margin)
            right = min(w, int(np.ceil(x2 * w)) + margin)
            bottom = min(h, int(np.ceil(y2 * h)) + margin)
            sharpened[top:bottom, left:right] = rgb[top:bottom, left:right]

    result = Image.fromarray(sharpened, "RGB")
    if "A" in image.getbands():
        result.putalpha(image.getchannel("A"))
    return result
