"""Source-guided *red flat-ink* colour repair after actual V2 SR (research only).

The uploaded V2 benchmark revealed that Real-ESRGAN invents blue/black
mottling inside small, solid-colour sign letters. Edge sharpening alone
cannot repair their colour. The original low-resolution RGB is therefore
used as a *photometric constraint*, not as OCR or inferred letter text.

This first conservative probe supports only strongly red, flat-colour ink.
It never changes photos, intact red blocks, gold curves, transparent alpha,
protected faces, or unrelated text colours. Disabled by default; NOT a
general Thai typography solution, and not approved for vinyl print.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image


def source_guided_red_ink(rgb: np.ndarray, source: np.ndarray, *,
                          alpha: np.ndarray | None = None,
                          protected_regions=(), strength: float = 1.0):
    """Return (reconstructed RGB, audit) with exact source-output dimensions.

    A robust dominant background colour and the LR *red/green, red/blue*
    mixture slopes define the original red ink palette. Core-stroke coverage
    is protected from the dark-mottled colour emitted by V2. The source
    preview also acts as a support mask, so a random red region in V2 cannot
    fabricate a new stroke outside the source.
    """
    if (not isinstance(rgb, np.ndarray) or not isinstance(source, np.ndarray)
            or rgb.dtype != np.uint8 or source.dtype != np.uint8
            or rgb.ndim != 3 or source.ndim != 3
            or rgb.shape[2] != 3 or source.shape[2] != 3):
        raise ValueError("Source-guided ink requires uint8 RGB images")
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Ink preservation strength must be finite 0..1")
    h, w = rgb.shape[:2]
    if alpha is not None and (alpha.shape != (h, w)
                              or alpha.dtype != np.uint8):
        raise ValueError("Alpha must be matching uint8 transparency")
    audit = {"eligible": False, "reason": "unchanged",
             "quality_certified": False, "changed_pixels_pct": 0.0}
    if min(h, w) < 64 or min(source.shape[:2]) < 32 or strength == 0:
        audit["reason"] = "disabled_or_small_raster"
        return rgb.copy(), audit

    base = rgb.astype(np.float32)
    smooth = cv2.GaussianBlur(base, (0, 0), 1.0)
    local_std = np.sqrt(np.maximum(
        cv2.GaussianBlur(base * base, (0, 0), 1.0)-smooth * smooth, 0
    ).mean(axis=2))
    if float(np.mean(local_std < 6)) < .76:
        audit["reason"] = "photographic_texture_keep_v2"
        return rgb.copy(), audit

    src = source.astype(np.float32)
    background = np.median(src.reshape(-1, 3), axis=0)
    sr, sg, sb = (src[..., 0], src[..., 1], src[..., 2])
    source_red = ((sr-sg > 40) & (sr-sb > 37) & (sr > 105))
    if int(source_red.sum()) < 40:
        audit["reason"] = "not_enough_source_red_ink"
        return rgb.copy(), audit

    r, g, b = (base[..., 0], base[..., 1], base[..., 2])
    red = (r-g > 50) & (r-b > 48) & (r > 110)
    prior = cv2.resize(source, (w, h), interpolation=cv2.INTER_CUBIC)
    prior = prior.astype(np.float32)
    support = ((prior[..., 0]-prior[..., 1] > 23)
               & (prior[..., 0]-prior[..., 2] > 23))
    support = cv2.dilate(support.astype(np.uint8),
                         np.ones((5, 5), np.uint8)) != 0
    red &= support
    if int(red.sum()) < 80:
        audit["reason"] = "source_red_stroke_not_confident"
        return rgb.copy(), audit
    core = cv2.erode(red.astype(np.uint8),
                     np.ones((3, 3), np.uint8)) != 0
    if alpha is not None:
        # The matte around PNG/TIFF cutouts must never be altered.
        opaque = cv2.erode((alpha == 255).astype(np.uint8),
                           np.ones((9, 9), np.uint8)) != 0
        core &= opaque
        red &= opaque
    for rect in protected_regions or ():
        if len(rect) != 4 or not all(math.isfinite(float(v)) for v in rect):
            raise ValueError("Invalid selected face rectangle")
        x1, y1, x2, y2 = map(float, rect)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Face ROI must be normalized 0..1")
        margin = max(8, round(min((x2-x1)*w, (y2-y1)*h)*.15))
        left = max(0, math.floor(x1*w)-margin)
        top = max(0, math.floor(y1*h)-margin)
        right = min(w, math.ceil(x2*w)+margin)
        bottom = min(h, math.ceil(y2*h)+margin)
        red[top:bottom, left:right] = False
        core[top:bottom, left:right] = False
    if int(core.sum()) < 15:
        audit["reason"] = "no_safe_stroke_core"
        return rgb.copy(), audit

    spread = np.percentile(r[core], 90)-np.percentile(r[core], 10)
    # Broad red blocks which are already flat do not need correction.
    if spread < 13:
        audit["reason"] = "already_uniform_flat_ink"
        return rgb.copy(), audit

    # Estimate the foreground from the brightest SR-red stroke pixel,
    # correcting for the frequently sub-full source coverage of thin glyphs.
    # Extrapolation is intentionally capped; it does not infer letter shapes.
    foreground_r = float(np.clip(
        background[0] + 1.12*(np.percentile(r[red], 99)-background[0]),
        0, 255
    ))
    residual_r = sr[source_red]-background[0]
    denominator = float(np.dot(residual_r, residual_r))+1e-4
    foreground_g = float(np.clip(
        background[1] + (np.dot(residual_r, sg[source_red]-background[1])
                        /denominator)*(foreground_r-background[0]), 0, 255
    ))
    foreground_b = float(np.clip(
        background[2] + (np.dot(residual_r, sb[source_red]-background[2])
                        /denominator)*(foreground_r-background[0]), 0, 255
    ))
    palette = np.array([foreground_r, foreground_g, foreground_b],
                       dtype=np.float32)
    direction = palette-background
    distance = float(np.dot(direction, direction))
    if distance < 1500:
        audit["reason"] = "ambiguous_ink_palette"
        return rgb.copy(), audit

    # Keep V2's existing antialias geometry, but constrain its colour to
    # the LR-supported background->ink colour line. Core pixels are repaired
    # more strongly; fractional edge coverage stays smooth.
    coverage = np.clip(
        np.sum((base-background)*direction, axis=2)/distance*.95,
        0.0, 1.0
    )
    # Do not over-darken valid anti-aliased thin strokes. The 0.85
    # projection from the first research attempt demonstrably worsened a
    # known-reference source with otherwise intact letter boundaries.
    coverage[core] = .95
    target = background + coverage[..., None]*direction
    result = rgb.copy()
    result[red] = np.rint(np.clip(
        base[red]*(1-strength)+target[red]*strength, 0, 255
    )).astype(np.uint8)
    changed = np.max(np.abs(result.astype(np.int16)
                            -rgb.astype(np.int16)), axis=2) > 3
    audit.update(eligible=True, reason="lr_constrained_red_ink",
                 changed_pixels_pct=round(float(changed.mean()*100), 4),
                 foreground_rgb=[round(float(v), 2) for v in palette],
                 stroke_variation=round(float(spread), 3))
    return result, audit


def restore_source_guided_ink(output: Image.Image, source: Image.Image, *,
                              protected_regions=(), strength: float = 1.0):
    """Pillow compatibility adapter. Preserve V2-sized alpha pixel for pixel."""
    rgb = np.asarray(output.convert("RGB"), dtype=np.uint8)
    original = np.asarray(source.convert("RGB"), dtype=np.uint8)
    alpha = (np.asarray(output.getchannel("A"), dtype=np.uint8)
             if "A" in output.getbands() else None)
    restored, audit = source_guided_red_ink(
        rgb, original, alpha=alpha, strength=strength,
        protected_regions=protected_regions
    )
    image = Image.fromarray(restored, "RGB")
    if alpha is not None:
        image.putalpha(output.getchannel("A"))
    return image, audit
