"""Print CMYK directly from a user-selected external ICC ZIP or directory.

Only the new NiyomSilp experimental modules are used; no GUI changes and no
profile extraction to disk. Adobe profile bytes are *not* committed to source.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .icc_library import read_cmyk_profile_by_sha
from .print_output import PrintSpec, export_print_image


def export_selected_cmyk(
    rendered: Image.Image | np.ndarray,
    output_path: str | Path,
    icc_source: str | Path,
    profile_sha256: str,
    dpi: int = 300,
    width: float | None = None,
    height: float | None = None,
    unit: str = "cm",
) -> dict:
    """Turn the chosen ZIP/directory ICC into an in-memory color transform.

    Supports CMYK TIFF/JPEG/PDF. No model inference, uploads or files in the
    input ZIP are changed. The returned report omits proprietary profile bytes.
    """
    raw_icc = read_cmyk_profile_by_sha(icc_source, profile_sha256)
    spec = PrintSpec(
        dpi=dpi, width=width, height=height, unit=unit,
        color_mode="CMYK", icc_profile=raw_icc
    )
    result = export_print_image(rendered, output_path, spec)
    return dict(result, icc_sha256=profile_sha256.lower(), from_external_source=True)
