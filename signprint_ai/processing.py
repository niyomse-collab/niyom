from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple
import math

import cv2
import numpy as np
from PIL import Image

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]


@dataclass
class EnhanceSettings:
    denoise: int = 48
    flat_smoothing: int = 52
    text_graphic_boost: int = 58
    contrast: int = 20
    sharpness: int = 46
    saturation: int = 6
    ai_scale: int = 4
    print_width: float | None = None
    print_height: float | None = None
    print_unit: str = "cm"
    dpi: int = 150
    resize_mode: str = "fit"  # fit | stretch
    export_format: str = "PNG"
    v1_baseline: bool = True


def _notify(cb: ProgressFn, value: int, label: str) -> None:
    if cb:
        cb(max(0, min(100, int(value))), label)


def _cancelled(cancel: CancelFn) -> None:
    if cancel and cancel():
        raise InterruptedError("Processing cancelled")


def unit_to_inches(value: float, unit: str) -> float:
    u = unit.lower()
    if u == "mm":
        return value / 25.4
    if u == "cm":
        return value / 2.54
    if u == "m":
        return value * 100.0 / 2.54
    if u in ("in", "inch", "inches"):
        return value
    if u in ("ft", "feet"):
        return value * 12.0
    raise ValueError(f"Unsupported unit: {unit}")


def print_pixels(width: float, height: float, unit: str, dpi: int) -> Tuple[int, int]:
    if width <= 0 or height <= 0 or dpi <= 0:
        raise ValueError("Print width, height and DPI must be positive")
    return (
        max(1, round(unit_to_inches(width, unit) * dpi)),
        max(1, round(unit_to_inches(height, unit) * dpi)),
    )


def _edge_map(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (0, 0), 0.7)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    p = float(np.percentile(mag, 95))
    if p < 1.0:
        p = 1.0
    edge = np.clip(mag / p, 0.0, 1.0)
    edge = cv2.GaussianBlur(edge, (0, 0), 0.75)
    return edge.astype(np.float32)


def _graphic_mask(rgb: np.ndarray, edge: np.ndarray) -> np.ndarray:
    """Find likely text/logo/graphic regions without OCR.

    We favor strong edges, saturated fills and compact local contrast.  The mask is
    deliberately soft so photographs are not turned into posterized artwork.
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat = hsv[..., 1].astype(np.float32) / 255.0
    val = hsv[..., 2].astype(np.float32) / 255.0

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    local = cv2.GaussianBlur(gray, (0, 0), 2.0)
    local_contrast = np.clip(np.abs(gray - local) * 5.0, 0.0, 1.0)

    # Saturated edge regions are common in signage text and logos.  Strong
    # achromatic edges (black/white letters) are kept through local_contrast.
    base = np.maximum(edge * (0.45 + 0.55 * sat), local_contrast * 0.75)
    base = np.maximum(base, edge * ((val < 0.22) | (val > 0.82)).astype(np.float32) * 0.65)

    hard = (base > 0.20).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, kernel, iterations=1)
    hard = cv2.dilate(hard, kernel, iterations=1)
    soft = cv2.GaussianBlur(hard.astype(np.float32) / 255.0, (0, 0), 1.0)
    return np.clip(soft, 0.0, 1.0)


def _pre_denoise(rgb: np.ndarray, strength: int) -> np.ndarray:
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))
    # Bilateral filtering preserves sign/text edges better than global Gaussian
    # blur and avoids the very high cost of NLM on banner-sized images.
    sigma_color = 15.0 + 65.0 * s
    sigma_space = 2.0 + 4.0 * s
    smooth = cv2.bilateralFilter(rgb, d=5, sigmaColor=sigma_color, sigmaSpace=sigma_space)
    # Chroma-only cleanup reduces AI/JPEG colored speckles while retaining luma edges.
    lab = cv2.cvtColor(smooth, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    k = 3 if strength < 65 else 5
    a2 = cv2.medianBlur(a, k)
    b2 = cv2.medianBlur(b, k)
    chroma = cv2.cvtColor(cv2.merge([l, a2, b2]), cv2.COLOR_LAB2RGB)
    amount = 0.35 + 0.45 * s
    out = cv2.addWeighted(rgb, 1.0 - amount, chroma, amount, 0)
    return out


def _flat_area_smoothing(rgb: np.ndarray, edge: np.ndarray, strength: int) -> np.ndarray:
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))
    sigma = 0.8 + 1.8 * s
    blur = cv2.GaussianBlur(rgb, (0, 0), sigma)

    # Blend heavily only in low-edge areas.  This removes grain from solid sign
    # backgrounds but does not smear text, logos, food edges, or faces.
    flat = np.clip(1.0 - edge * (2.6 - 0.8 * s), 0.0, 1.0)
    flat = cv2.GaussianBlur(flat, (0, 0), 1.2)
    alpha = (0.12 + 0.58 * s) * flat[..., None]
    out = rgb.astype(np.float32) * (1.0 - alpha) + blur.astype(np.float32) * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _local_contrast(rgb: np.ndarray, strength: int) -> np.ndarray:
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.15 + 1.35 * s, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    lmix = cv2.addWeighted(l, 1.0 - (0.25 + 0.45 * s), l2, 0.25 + 0.45 * s, 0)
    return cv2.cvtColor(cv2.merge([lmix, a, b]), cv2.COLOR_LAB2RGB)


def _saturation(rgb: np.ndarray, strength: int) -> np.ndarray:
    if strength == 0:
        return rgb
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    factor = 1.0 + max(-100, min(100, strength)) / 250.0
    hsv[..., 1] *= factor
    hsv[..., 1] = np.clip(hsv[..., 1], 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def _graphic_solidify(rgb: np.ndarray, mask: np.ndarray, strength: int) -> np.ndarray:
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))

    # A small median pass suppresses one-pixel speckles inside lettering.  Blend
    # it only under the text/graphic mask so photo texture remains untouched.
    median = cv2.medianBlur(rgb, 3)
    alpha = mask[..., None] * (0.10 + 0.30 * s)
    base = rgb.astype(np.float32) * (1.0 - alpha) + median.astype(np.float32) * alpha

    # Reinforce local color separation around graphic edges without expanding
    # glyph shapes.  The clipped high-pass avoids white/black halos.
    blur = cv2.GaussianBlur(base, (0, 0), 1.05)
    detail = base - blur
    limit = 5.0 + 12.0 * s
    detail = np.clip(detail, -limit, limit)
    gain = mask[..., None] * (0.25 + 0.75 * s)
    out = base + detail * gain
    return np.clip(out, 0, 255).astype(np.uint8)


def _anti_halo_sharpen(rgb: np.ndarray, edge: np.ndarray, strength: int) -> np.ndarray:
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))
    src = rgb.astype(np.float32)
    blur = cv2.GaussianBlur(src, (0, 0), 0.75 + 0.55 * s)
    detail = src - blur
    # Threshold low-amplitude noise and clamp extreme halo-producing detail.
    threshold = 1.6 + 2.5 * (1.0 - s)
    detail[np.abs(detail) < threshold] = 0
    detail = np.clip(detail, -(7.0 + 12.0 * s), 7.0 + 12.0 * s)
    edge_gain = (0.20 + 0.80 * edge)[..., None]
    out = src + detail * edge_gain * (0.55 + 1.15 * s)
    return np.clip(out, 0, 255).astype(np.uint8)


def _selective_flat_denoise(rgb: np.ndarray, strength: int) -> np.ndarray:
    """Reduce colored speckles mainly in flat areas while protecting texture/edges."""
    if strength <= 0:
        return rgb
    s = max(0.0, min(1.0, strength / 100.0))
    edge = _edge_map(rgb)
    cleaned = _pre_denoise(rgb, max(1, round(strength * 0.45)))
    flat = np.clip(1.0 - edge * 3.2, 0.0, 1.0)
    flat = cv2.GaussianBlur(flat, (0, 0), 1.0)
    alpha = flat[..., None] * (0.08 + 0.28 * s)
    out = rgb.astype(np.float32) * (1.0 - alpha) + cleaned.astype(np.float32) * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def enhance_detail_preserving(
    rgb: np.ndarray,
    settings: EnhanceSettings,
    progress: ProgressFn = None,
    cancel: CancelFn = None,
    start_progress: int = 65,
) -> np.ndarray:
    """V1-style finishing pipeline: preserve micro-detail first, clean only where safe.

    The user sliders remain 0-100, but the effective strength is intentionally
    conservative so even high settings do not smear food texture or small Thai text.
    """
    _cancelled(cancel)
    _notify(progress, start_progress, "รักษารายละเอียดและวิเคราะห์พื้นที่เรียบ")
    out = rgb

    # Denoise only where edge energy is low; never globally blur the upscaled image.
    denoise_eff = round(settings.denoise * 0.55)
    out = _selective_flat_denoise(out, denoise_eff)

    _cancelled(cancel)
    _notify(progress, start_progress + 7, "เกลี่ยพื้นสีเฉพาะบริเวณเรียบ")
    edge = _edge_map(out)
    flat_eff = round(settings.flat_smoothing * 0.38)
    out = _flat_area_smoothing(out, edge, flat_eff)

    _cancelled(cancel)
    _notify(progress, start_progress + 13, "เพิ่มมิติแบบไม่บดรายละเอียด")
    contrast_eff = round(settings.contrast * 0.45)
    out = _local_contrast(out, contrast_eff)
    out = _saturation(out, round(settings.saturation * 0.70))

    _cancelled(cancel)
    _notify(progress, start_progress + 18, "รักษาขอบตัวอักษรและโลโก้")
    edge = _edge_map(out)
    gmask = _graphic_mask(out, edge)
    text_eff = round(settings.text_graphic_boost * 0.52)
    out = _graphic_solidify(out, gmask, text_eff)

    _cancelled(cancel)
    _notify(progress, start_progress + 23, "เพิ่มความคมแบบ Anti-Halo")
    edge = _edge_map(out)
    sharp_eff = round(settings.sharpness * 0.58)
    out = _anti_halo_sharpen(out, edge, sharp_eff)
    return out


def enhance_rgb(rgb: np.ndarray, settings: EnhanceSettings, progress: ProgressFn = None, cancel: CancelFn = None) -> np.ndarray:
    _cancelled(cancel)
    _notify(progress, 3, "วิเคราะห์ขอบและพื้นที่สี")
    edge0 = _edge_map(rgb)

    _cancelled(cancel)
    _notify(progress, 10, "ลด Noise ก่อนขยาย")
    out = _pre_denoise(rgb, settings.denoise)

    _cancelled(cancel)
    _notify(progress, 18, "ทำพื้นสีให้เรียบแบบรักษาขอบ")
    edge1 = _edge_map(out)
    out = _flat_area_smoothing(out, edge1, settings.flat_smoothing)

    _cancelled(cancel)
    _notify(progress, 25, "ปรับคอนทราสต์เฉพาะรายละเอียด")
    out = _local_contrast(out, settings.contrast)
    out = _saturation(out, settings.saturation)

    _cancelled(cancel)
    _notify(progress, 32, "ตรวจจับตัวอักษรและกราฟิก")
    edge2 = _edge_map(out)
    gmask = _graphic_mask(out, edge2)

    _cancelled(cancel)
    _notify(progress, 38, "เกลี่ยสีตัวอักษรและโลโก้")
    out = _graphic_solidify(out, gmask, settings.text_graphic_boost)

    _cancelled(cancel)
    _notify(progress, 44, "เพิ่มความคมแบบป้องกัน Halo")
    edge3 = _edge_map(out)
    out = _anti_halo_sharpen(out, edge3, settings.sharpness)
    return out


def final_resize(rgb: np.ndarray, target_size: Tuple[int, int] | None) -> np.ndarray:
    if not target_size:
        return rgb
    tw, th = target_size
    h, w = rgb.shape[:2]
    if (w, h) == (tw, th):
        return rgb
    interpolation = cv2.INTER_AREA if tw < w or th < h else cv2.INTER_LANCZOS4
    return cv2.resize(rgb, (tw, th), interpolation=interpolation)


def save_image(rgb: np.ndarray, output_path: str | Path, dpi: int = 150, alpha: np.ndarray | None = None) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if alpha is not None:
        if alpha.shape[:2] != rgb.shape[:2]:
            alpha = cv2.resize(alpha, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LANCZOS4)
        rgba = np.dstack([rgb, alpha])
        img = Image.fromarray(rgba, mode="RGBA")
    else:
        img = Image.fromarray(rgb, mode="RGB")

    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        if img.mode != "RGB":
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.getchannel("A"))
            img = bg
        img.save(path, quality=96, subsampling=0, dpi=(dpi, dpi))
    elif ext in (".tif", ".tiff"):
        img.save(path, compression="tiff_lzw", dpi=(dpi, dpi))
    elif ext == ".pdf":
        if img.mode != "RGB":
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.getchannel("A"))
            img = bg
        img.save(path, "PDF", resolution=float(dpi))
    else:
        img.save(path, dpi=(dpi, dpi), compress_level=3)


def load_image(path: str | Path) -> tuple[np.ndarray, np.ndarray | None]:
    pil = Image.open(path)
    alpha = None
    if pil.mode in ("RGBA", "LA") or (pil.mode == "P" and "transparency" in pil.info):
        rgba = pil.convert("RGBA")
        arr = np.asarray(rgba)
        alpha = arr[..., 3].copy()
        rgb = arr[..., :3].copy()
    else:
        rgb = np.asarray(pil.convert("RGB")).copy()
    return rgb, alpha
