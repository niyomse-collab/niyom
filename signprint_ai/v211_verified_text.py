"""Verified exact-text typography reconstruction for V2.1.1 (opt-in).

Raster AI cannot guarantee an original Thai vowel, tone mark, phone number or
letter shape once source pixels are genuinely missing. When the shop has the
EXACT customer's text and an installed matching font, bypass neural guesses:
render the supplied Unicode through HarfBuzz/RAQM at final print dimensions.

This feature never OCRs, fabricates text, adds an opaque background to cutouts,
or changes image dimensions. Text-only transparent overlays are always safe.
Replacing existing ink is allowed ONLY inside an explicitly selected flat-
background rectangle whose outside ring is verified; photos/gradients fail
closed rather than being painted over. No proprietary font files are shipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont, features


@dataclass(frozen=True)
class VerifiedTextRegion:
    x: int
    y: int
    width: int
    height: int
    text: str
    font_path: str
    max_font_px: int
    fill: tuple[int, int, int] = (255, 255, 255)
    align: str = "center"
    mode: str = "replace_flat"  # replace_flat | transparent_overlay


def _validate(region: VerifiedTextRegion, image_size: tuple[int, int]) -> None:
    w, h = image_size
    values = (region.x, region.y, region.width, region.height, region.max_font_px)
    if (not all(isinstance(n, int) for n in values)
            or min(region.x, region.y) < 0
            or min(region.width, region.height, region.max_font_px) <= 0
            or region.x + region.width > w
            or region.y + region.height > h):
        raise ValueError("Text ROI coordinates exceed final print canvas")
    if (not isinstance(region.text, str) or not region.text.strip()
            or "\x00" in region.text or len(region.text) > 10000):
        raise ValueError("Exact supplied text is required; no OCR guessing")
    if region.align not in ("center", "left", "right"):
        raise ValueError("Horizontal text alignment must be left/center/right")
    if region.mode not in ("replace_flat", "transparent_overlay"):
        raise ValueError("Text region mode must be replace_flat/transparent_overlay")
    if (len(region.fill) != 3
            or not all(isinstance(c, int) and 0 <= c <= 255
                       for c in region.fill)):
        raise ValueError("Ink RGB fill must have three 8-bit components")
    if not features.check("raqm"):
        raise RuntimeError("Verified Thai typography requires HarfBuzz/RAQM shaping")
    if not Path(region.font_path).is_file():
        raise FileNotFoundError("Select an existing installed matching font")


def exact_text_overlay(
    canvas_size: tuple[int, int],
    region: VerifiedTextRegion,
    *,
    supersample: int = 3,
) -> tuple[Image.Image, dict]:
    """Draw exact customer text to transparent RGBA, with no opaque matte."""
    _validate(region, canvas_size)
    if supersample not in (2, 3, 4):
        raise ValueError("Text supersampling must be 2, 3 or 4")
    s = supersample
    tw, th = region.width*s, region.height*s
    if tw * th > 100_000_000:
        raise ValueError("Selected text ROI exceeds bounded render memory")
    pad = max(2*s, round(min(tw, th)*.03))
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    for size in range(region.max_font_px, 3, -1):
        font = ImageFont.truetype(
            region.font_path, size*s, layout_engine=ImageFont.Layout.RAQM
        )
        l, t, r, b = measure.multiline_textbbox(
            (0, 0), region.text, font=font, spacing=size*s//4
        )
        ink_width, ink_height = r-l, b-t
        if ink_width <= tw-2*pad and ink_height <= th-2*pad:
            break
    else:
        raise ValueError("Exact text cannot fit without stretching or cropping")
    mask = Image.new("L", (tw, th), 0)
    draw = ImageDraw.Draw(mask)
    x = (pad if region.align == "left" else
         tw-pad-ink_width if region.align == "right" else
         (tw-ink_width)/2)
    y = (th-ink_height)/2
    draw.multiline_text(
        (round(x-l), round(y-t)), region.text, fill=255, font=font,
        spacing=size*s//4
    )
    alpha = mask.resize(
        (region.width, region.height), Image.Resampling.LANCZOS
    )
    patch = Image.new("RGBA", (region.width, region.height),
                      (*region.fill, 0))
    patch.putalpha(alpha)
    result = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    result.paste(patch, (region.x, region.y))
    return result, {
        "exact_text": region.text,
        "font_size_px": size,
        "shaping": "RAQM_HarfBuzz",
        "verified_user_text": True,
        "no_background_generated": True,
        "print_dimensions_unchanged": True,
        "quality_certified_without_human_proof": False,
    }


def replace_on_verified_flat_background(
    image: Image.Image,
    region: VerifiedTextRegion,
    *,
    max_border_error: float = 9.0,
) -> tuple[Image.Image, dict]:
    """Overwrite only a confirmed opaque and uniform text rectangle.

    No image segmentation guesswork: mixed/photo/gradient/transparent input
    fails closed. Caller can instead export exact_text_overlay and position
    that layer manually in Photoshop without any destructive filling.
    """
    _validate(region, image.size)
    if max_border_error <= 0 or not math.isfinite(max_border_error):
        raise ValueError("Invalid flat-background confidence threshold")
    pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    x, y, w, h = region.x, region.y, region.width, region.height
    margin = max(3, min(10, min(w, h)//8))
    x0, y0 = max(0, x-margin), max(0, y-margin)
    x1, y1 = min(image.width, x+w+margin), min(image.height, y+h+margin)
    outside = pixels[y0:y1, x0:x1]
    ring_mask = np.ones(outside.shape[:2], bool)
    ring_mask[y-y0:y+h-y0, x-x0:x+w-x0] = False
    surrounding = outside[ring_mask]
    if len(surrounding) < 24:
        raise ValueError("Insufficient exterior pixels to verify flat backdrop")
    if (np.any(surrounding[:, 3] != 255)
            or np.any(pixels[y:y+h, x:x+w, 3] != 255)):
        raise ValueError("Transparent cutout: use text-only RGBA overlay")
    background = np.median(surrounding[:, :3].astype(float), axis=0)
    errors = np.max(
        np.abs(surrounding[:, :3].astype(float)-background), axis=1
    )
    if np.quantile(errors, .98) > max_border_error:
        raise ValueError(
            "Nonuniform/photo/gradient exterior: refuse destructive replacement"
        )
    painted = pixels.copy()
    painted[y:y+h, x:x+w, :3] = np.uint8(np.rint(background))
    overlay, audit = exact_text_overlay(image.size, region)
    out = Image.alpha_composite(Image.fromarray(painted, "RGBA"), overlay)
    return out, dict(
        audit, background_rgb=[round(float(v)) for v in background],
        unchanged_outside_selected_rectangle=True,
    )


def apply_verified_regions(
    image: Image.Image,
    regions: tuple[VerifiedTextRegion, ...],
) -> tuple[Image.Image, list[dict]]:
    """Apply explicit ROI operations on final raster; V2 portrait untouched."""
    result = image.copy()
    audits = []
    for region in regions:
        if region.mode == "transparent_overlay":
            overlay, audit = exact_text_overlay(result.size, region)
            result = Image.alpha_composite(result.convert("RGBA"), overlay)
        else:
            result, audit = replace_on_verified_flat_background(result, region)
        audits.append(audit)
    return result, audits
