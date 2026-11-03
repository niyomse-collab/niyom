"""Conservative four-engine research fusion; not production quality certification.

All candidates must already pass validate_candidate. Pixel averaging is
deliberately avoided: it can create double edges and corrupt lettering.
This selects the least-deviating complete candidate relative to a trusted
V2 reference, and falls back to V2 when the threshold is exceeded.
Selection is NOT proof of improved visual quality.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from tools.v211_four_engine_coordinator import ENGINES, validate_candidate


def select_conservative_candidate(
    source: Path,
    v2_reference: Path,
    candidates: dict[str, Path],
    output: Path,
    *,
    max_mean_absolute_delta: float = 12.0,
) -> dict:
    if set(candidates) != set(ENGINES):
        raise ValueError("All four real engine candidates are required")
    with Image.open(v2_reference) as base:
        if base.mode not in ("RGB", "RGBA"):
            raise ValueError("V2 reference must be RGB or RGBA")
        size, mode = base.size, base.mode
        base_pixels = np.asarray(base).astype(np.int16)
        base_icc = base.info.get("icc_profile")
        base_dpi = base.info.get("dpi")
    scores = {}
    for engine in ENGINES:
        path = Path(candidates[engine])
        validate_candidate(source, path, size)
        with Image.open(path) as im:
            if im.mode != mode or im.info.get("icc_profile") != base_icc:
                raise ValueError(engine + ": differs from V2 color contract")
            pixels = np.asarray(im).astype(np.int16)
        scores[engine] = float(np.abs(pixels[..., :3] - base_pixels[..., :3]).mean())
    selected = min(ENGINES, key=lambda name: scores[name])
    accepted = scores[selected] <= max_mean_absolute_delta
    chosen_path = Path(candidates[selected]) if accepted else Path(v2_reference)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(chosen_path) as chosen:
        save_kwargs = {}
        if base_icc is not None:
            save_kwargs["icc_profile"] = base_icc
        if base_dpi is not None:
            save_kwargs["dpi"] = base_dpi
        chosen.save(output, format="PNG", **save_kwargs)
    return {
        "four_real_candidates_required": True,
        "candidate_delta_from_v2": scores,
        "selected": selected if accepted else "v2_fallback",
        "output": str(output),
        "quality_certified": False,
        "fusion_type": "conservative_selection_not_pixel_blending",
    }
