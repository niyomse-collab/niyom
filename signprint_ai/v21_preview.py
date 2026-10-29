"""Fast and truthful V2.1 preview of the export-time finishing controls.

This intentionally does not run expensive AI upscaling or CMYK/ICC conversion.
The caller must label it as a finishing-only thumbnail, never a print proof.
"""
from __future__ import annotations

from PIL import Image

from .v2_graphic_edges import refine_sign_edges


def render_finishing_preview(image: Image.Image, settings) -> Image.Image:
    """Apply the same slider-based finishing used on the final AI raster."""
    regions = (settings.face_regions if settings.face_protection else None)
    return refine_sign_edges(image, settings=settings, protected_regions=regions)
