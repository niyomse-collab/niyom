"""NiyomSilp-owned print finalizer; NOT connected to the existing desktop UI."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image, ImageCms, ImageOps

_INCHES = {"mm": 1/25.4, "cm": 1/2.54, "m": 100/2.54,
           "in": 1, "inch": 1, "inches": 1, "ft": 12, "feet": 12}
_FORMATS = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".pdf"}


def open_cmyk_output_profile(path: str | Path | bytes):
    """Reject RGB, broken or unrelated ICC files before rendering output."""
    if isinstance(path, bytes):
        if not path or len(path) > 10_000_000:
            raise ValueError("CMYK ICC profile bytes missing or too large")
        try:
            profile = ImageCms.ImageCmsProfile(BytesIO(path))
        except Exception as exc:
            raise ValueError(f"Cannot open ICC output profile: {exc}") from exc
    else:
        file = Path(path)
        if not file.is_file():
            raise ValueError(f"Valid CMYK ICC output profile is required: {file}")
        try:
            profile = ImageCms.getOpenProfile(str(file))
        except Exception as exc:
            raise ValueError(f"Cannot open ICC output profile: {exc}") from exc
    try:
        space = str(profile.profile.xcolor_space).strip().upper()
    except Exception as exc:
        raise ValueError(f"Cannot open ICC output profile: {exc}") from exc
    if space != "CMYK":
        raise ValueError(f"ICC must be CMYK output profile, got {space}")
    if str(profile.profile.device_class).strip().lower() != "prtr":
        raise ValueError("ICC must be a CMYK printer/output profile")
    return profile


@dataclass(frozen=True)
class PrintSpec:
    dpi: int = 150
    width: float | None = None
    height: float | None = None
    unit: str = "cm"
    color_mode: str = "RGB"
    icc_profile: str | Path | bytes | None = None

    def target_pixels(self) -> tuple[int, int] | None:
        if not isinstance(self.dpi, int) or self.dpi <= 0:
            raise ValueError("DPI must be positive integer")
        if self.width is None and self.height is None:
            return None
        if self.width is None or self.height is None:
            raise ValueError("Both print dimensions are required")
        if not (0 < self.width < float("inf") and 0 < self.height < float("inf")):
            raise ValueError("Print dimensions must be positive and finite")
        factor = _INCHES.get(self.unit.lower())
        if factor is None:
            raise ValueError("Invalid print unit")
        w = max(1, round(self.width * factor * self.dpi))
        h = max(1, round(self.height * factor * self.dpi))
        if max(w, h) > 30000:
            raise ValueError("30,000 pixel dimension limit")
        return w, h


def fit_rgb_to_print(image: Image.Image, target: tuple[int, int] | None) -> Image.Image:
    """Do not distort customer lettering: contain and white-letterbox."""
    source = image.convert("RGB")
    if target is None or source.size == target:
        return source
    if min(target) <= 0 or max(target) > 30000:
        raise ValueError("Invalid target pixel size")
    resized = ImageOps.contain(source, target, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target, "white")
    canvas.paste(resized, ((target[0]-resized.width)//2, (target[1]-resized.height)//2))
    return canvas


def export_print_image(pixels: Image.Image | np.ndarray, destination: str | Path,
                       spec: PrintSpec = PrintSpec()) -> dict:
    """Export only after inference; use a user-supplied valid ICC for CMYK."""
    path = Path(destination)
    suffix = path.suffix.lower()
    if suffix not in _FORMATS:
        raise ValueError("Unsupported print format")
    color = spec.color_mode.upper()
    if color not in {"RGB", "CMYK"}:
        raise ValueError("Unsupported color mode")
    if color == "CMYK" and suffix == ".png":
        raise ValueError("CMYK cannot be exported as PNG")
    target = spec.target_pixels()
    profile_bytes = None
    opened_profile = None
    if color == "CMYK":
        if not spec.icc_profile:
            raise ValueError("Valid CMYK ICC profile is required")
        opened_profile = open_cmyk_output_profile(spec.icc_profile)
        profile_bytes = (
            spec.icc_profile if isinstance(spec.icc_profile, bytes)
            else Path(spec.icc_profile).read_bytes()
        )
    source = pixels if isinstance(pixels, Image.Image) else Image.fromarray(np.asarray(pixels))
    out = fit_rgb_to_print(source, target)
    if profile_bytes is not None:
        try:
            out = ImageCms.profileToProfile(
                out, ImageCms.createProfile("sRGB"), opened_profile,
                renderingIntent=0, outputMode="CMYK"
            )
        except Exception as exc:
            raise ValueError(f"ICC conversion failed: {exc}") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"dpi": (spec.dpi, spec.dpi)}
    if profile_bytes is not None:
        options["icc_profile"] = profile_bytes
    if suffix == ".png":
        out.save(path, "PNG", compress_level=3, **options)
    elif suffix in {".tif", ".tiff"}:
        out.save(path, "TIFF", compression="tiff_lzw", **options)
    elif suffix in {".jpg", ".jpeg"}:
        out.save(path, "JPEG", quality=96, subsampling=0, **options)
    else:
        options.pop("dpi", None)
        out.save(path, "PDF", resolution=float(spec.dpi), **options)
    return {"path": str(path), "pixels": out.size, "mode": out.mode, "dpi": spec.dpi}
