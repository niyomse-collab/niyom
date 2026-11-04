"""V2.1.1 research integration: let four installed AIs assist the V2 raster.

This opt-in-to-install (NOT opt-in-to-run) adapter does not change V2 controls,
sizing or export. It works on the finished in-memory V2 RGB(A) raster *before*
existing V2 colour-management/export functions run.

The experimental 2x CLI engines receive a temporary resampled source at half
the requested output size. Odd pixel dimensions use an edge-extended reference;
the final result is cropped to exactly the user's arbitrary output dimensions.
The V2 raster anchors colours, alpha and face protection. Real four-engine
inference and visual quality on the shop GPU are still release gates.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageOps

from .v211_auto_setup import default_manifest

_LOG = logging.getLogger(__name__)

# Initial in-memory safety budget; large-format tile streaming is a separate
# release requirement. Never pretend large images received four-model help.
_MAX_IN_MEMORY_PIXELS = 18_000_000


def _padded_reference(image: Image.Image) -> Image.Image:
    """Pad only at the right/bottom, repeating edge pixels to even dimensions."""
    w, h = image.size
    W, H = w + (w % 2), h + (h % 2)
    if (W, H) == (w, h):
        return image.copy()
    padded = Image.new(image.mode, (W, H))
    padded.paste(image, (0, 0))
    if W != w:
        padded.paste(image.crop((w - 1, 0, w, h)), (w, 0))
    if H != h:
        padded.paste(image.crop((0, h - 1, w, h)), (0, h))
    if W != w and H != h:
        padded.putpixel((w, h), image.getpixel((w - 1, h - 1)))
    return padded


def maybe_enhance_v2_image(
    source: str | Path,
    v2_image: Image.Image,
    *,
    use_ai: bool = True,
    cancel: Callable[[], bool] | None = None,
    protected_regions: tuple = (),
    preserve_all_v2_faces: bool = False,
) -> tuple[Image.Image, dict]:
    """Try the four real engines without altering the pre-existing V2 raster.

    On success, return an enhanced raster ready for the SAME V2 export path.
    On any uncertainty, return the untouched V2 raster and an explicit status.
    Never pretend synthetic/CI tests establish production image quality.
    """
    base = v2_image
    preserved = {"v2_output_preserved": True, "four_engines_applied": False}
    if not use_ai or os.environ.get("NIYOMSIL_V211_FOUR_AI") == "0":
        return base, {**preserved, "status": "disabled"}
    if cancel and cancel():
        raise InterruptedError("Processing stopped by user")
    if base.mode not in ("RGB", "RGBA") or min(base.size) < 2:
        return base, {**preserved, "status": "unsupported_image_mode_or_size"}
    if base.width * base.height > _MAX_IN_MEMORY_PIXELS:
        return base, {**preserved, "status": "large_image_tiling_pending"}
    name = os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip()
    manifest = Path(name) if name else default_manifest()
    if not manifest.is_file():
        return base, {**preserved, "status": "models_not_installed"}

    try:
        from tools.v211_four_engine_run import run
        with tempfile.TemporaryDirectory(prefix="niyomsil-v211-background-") as td:
            folder = Path(td)
            padded = _padded_reference(base)
            original = Image.open(source)
            try:
                with ImageOps.exif_transpose(original) as oriented:
                    seed = oriented.convert(base.mode).resize(
                        (padded.width // 2, padded.height // 2),
                        Image.Resampling.LANCZOS,
                    )
            finally:
                original.close()
            # Face-protected alpha is owned by V2. Native 2x engines may
            # discard alpha; the coordinator reconstructs and validates it.
            if base.mode == "RGBA":
                seed.putalpha(padded.getchannel("A").resize(
                    seed.size, Image.Resampling.LANCZOS,
                ))
            metadata = {k: base.info[k] for k in ("icc_profile", "dpi") if k in base.info}
            seed_path, baseline_path = folder / "seed.png", folder / "v2.png"
            seed.save(seed_path, format="PNG", **metadata)
            padded.save(baseline_path, format="PNG", **metadata)
            result = run(
                seed_path, folder / "four", manifest, padded.size,
                real_engines=True, v2_reference=baseline_path,
                protected_regions=protected_regions,
                preserve_all_v2_faces=preserve_all_v2_faces,
            )
            fusion = result.get("four_engine_fusion") or {}
            if (result.get("completed_engine_count") != 4
                    or result.get("failures")
                    or not fusion.get("fusion_implemented")
                    or not fusion.get("output")):
                return base, {
                    **preserved, "status": "four_engine_incomplete",
                    "completed_engine_count": result.get("completed_engine_count", 0),
                    "failures": result.get("failures", {}),
                    "fusion_error": result.get("fusion_error"),
                }
            with Image.open(fusion["output"]) as image:
                image.load()
                candidate = image.crop((0, 0, base.width, base.height))
            if candidate.mode != base.mode or candidate.size != base.size:
                raise ValueError("four-AI fusion changed image geometry or mode")
            if base.mode == "RGBA":
                if candidate.getchannel("A").tobytes() != base.getchannel("A").tobytes():
                    raise ValueError("four-AI fusion modified V2 transparency")
            # Image fusion intentionally preserves V2 fills, but may make no
            # improvement on flat/face-protected images. Report that honestly.
            if not np.any(np.asarray(candidate) != np.asarray(base)):
                return base, {
                    **preserved, "status": "four_engine_no_pixel_effect",
                    "completed_engine_count": 4,
                }
            if cancel and cancel():
                raise InterruptedError("Processing stopped by user")
            candidate.info.update(base.info)
            return candidate, {
                "status": "four_engine_applied_to_v2_raster",
                "four_engines_applied": True,
                "completed_engine_count": 4,
                "v2_output_preserved": False,
                "fusion_implemented": True,
                "quality_certified": False,
                "engine_detail_contribution_mean_abs":
                    fusion.get("engine_detail_contribution_mean_abs", {}),
            }
    except InterruptedError:
        raise
    except Exception as exc:
        _LOG.warning("V2.1.1 four-engine background enhancement skipped: %s", exc)
        return base, {
            **preserved, "status": "four_engine_error",
            "error": type(exc).__name__ + ": " + str(exc),
        }
