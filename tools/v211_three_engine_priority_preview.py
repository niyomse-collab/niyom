"""Owner-led three-engine A/B preview; optional Anime4K never replaces gradients.

Select from Real-ESRGAN, Waifu2x, and Real-CUGAN. This is an *experimental*
one-whole-candidate preview, not claimed quality improvement or automatic
reconstruction. Never modify the original V2 print image or crop/retype text.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from tools.v211_four_engine_coordinator import validate_candidate

PRIMARY_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")
OPTIONAL_ENGINE = "anime4k"


def select_three_engine_preview(
    source: Path,
    v2_reference: Path,
    candidates: dict[str, Path],
    output: Path,
    *,
    max_mean_absolute_delta: float = 14.0,
    max_gradient_mismatch: float = 20.0,
) -> dict:
    """Emit a private A/B preview while retaining V2 as final print output.

    A candidate can be selected only if its geometry, alpha, ICC and RGB mode
    match V2 and its total color/gradient divergence is bounded. Divergence is
    NOT a perceptual quality score and cannot certify a print release.
    """
    if not set(PRIMARY_ENGINES).issubset(candidates):
        raise ValueError("All three priority engines required; Anime4K is optional")
    if not 0 <= max_mean_absolute_delta <= 255 or not 0 <= max_gradient_mismatch <= 255:
        raise ValueError("invalid image divergence threshold")
    source, baseline, output = Path(source), Path(v2_reference), Path(output)
    if baseline.resolve() == output.resolve():
        raise ValueError("preview cannot overwrite trusted V2 output")
    if source.resolve() == output.resolve():
        raise ValueError("preview cannot overwrite source")

    with Image.open(baseline) as base:
        if base.format != "PNG" or base.mode not in ("RGB", "RGBA"):
            raise ValueError("V2 reference must be RGB/RGBA PNG")
        size, mode = base.size, base.mode
        metadata = {
            key: base.info[key] for key in ("dpi", "icc_profile")
            if key in base.info
        }
        pixels_v2 = np.asarray(base.convert("RGB"), dtype=np.int16)
        base_alpha = base.getchannel("A").tobytes() if mode == "RGBA" else None

    def gradient_mismatch(a: np.ndarray, b: np.ndarray) -> float:
        # Mean absolute error in finite differences across both orientations.
        # Unlike a plain color MAE, gradient mismatch exposes locally flattened
        # color ramps or double-edges. It is not a complete quality metric.
        dh = np.abs((a[:, 1:] - a[:, :-1]) - (b[:, 1:] - b[:, :-1])).mean() if a.shape[1] > 1 else 0.0
        dv = np.abs((a[1:] - a[:-1]) - (b[1:] - b[:-1])).mean() if a.shape[0] > 1 else 0.0
        return (float(dh) + float(dv)) / 2.0

    scores: dict[str, dict[str, float | bool]] = {}
    for engine in PRIMARY_ENGINES:
        path = Path(candidates[engine])
        validate_candidate(source, path, size)
        with Image.open(path) as image:
            if image.mode != mode:
                raise ValueError(engine + ": colour/alpha mode differs from V2")
            if image.info.get("icc_profile") != metadata.get("icc_profile"):
                raise ValueError(engine + ": ICC differs from V2")
            if mode == "RGBA" and image.getchannel("A").tobytes() != base_alpha:
                raise ValueError(engine + ": transparency differs from V2")
            color = np.asarray(image.convert("RGB"), dtype=np.int16)
        mae = float(np.abs(color - pixels_v2).mean())
        gradients = gradient_mismatch(color, pixels_v2)
        scores[engine] = {
            "mean_color_delta": round(mae, 4),
            "gradient_mismatch": round(gradients, 4),
            "within_safety_bounds": mae <= max_mean_absolute_delta and gradients <= max_gradient_mismatch,
        }

    safe = [name for name in PRIMARY_ENGINES if scores[name]["within_safety_bounds"]]
    chosen = (
        min(safe, key=lambda name: (
            scores[name]["gradient_mismatch"],
            scores[name]["mean_color_delta"],
            PRIMARY_ENGINES.index(name),
        ))
        if safe else "v2_fallback"
    )
    chosen_path = baseline if chosen == "v2_fallback" else Path(candidates[chosen])
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(chosen_path) as preview:
        # Re-encode preserves pixel data; restore V2's print metadata exactly.
        preview.save(output, format="PNG", **metadata)

    return {
        "selected": chosen,
        "primary_engines": list(PRIMARY_ENGINES),
        "optional_anime4k_excluded_from_selection": True,
        "scores_relative_to_v2_not_absolute_quality": scores,
        "quality_certified": False,
        "fusion_implemented": False,
        "preview_not_print_export": True,
        "v2_reference_not_modified": True,
        "output": str(output),
    }
