"""Four *real* engine candidate detail-fusion into a separate V2.1.1 QA PNG.

Uses validated, independently executed Real-ESRGAN, Waifu2x, Real-CUGAN and
Anime4K candidate pixels. Only candidate high-frequency luminance details are
blended into approved V2 colour, not averaged RGB or retyped text. Flat colour,
smooth gradients, original ICC/DPI and the exact V2 RGBA alpha are retained.
Optional protected face regions are copied bit-for-bit from V2. This is NOT
quality approval: human A/B assessment against V2 remains required.
"""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile
import os

import numpy as np
from PIL import Image, ImageFilter

from tools.v211_four_engine_coordinator import ENGINES, validate_candidate

# Conservative detail weights: 3 Windows-verified favourite models dominate.
WEIGHTS = {"real_esrgan": 0.37, "waifu2x": 0.28, "real_cugan": 0.35}
ANIME4K_DETAIL_WEIGHT = 0.06
TILE = 384
HALO = 8
MAX_DETAIL_CHANGE = 6.0


def _gray_highpass(region: Image.Image) -> np.ndarray:
    gray = region.convert("L")
    lum = np.asarray(gray, dtype=np.float32)
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=1.0))
    return lum - np.asarray(blurred, dtype=np.float32)


def _protected_mask(x0: int, y0: int, w: int, h: int,
                    size: tuple[int, int],
                    normalized_regions: tuple[tuple[float, float, float, float], ...]) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    W, H = size
    for coords in normalized_regions:
        if len(coords) != 4 or not all(np.isfinite(value) and 0 <= value <= 1 for value in coords):
            raise ValueError("invalid face protection rectangle")
        a, b, c, d = coords
        if a >= c or b >= d:
            raise ValueError("inverted face rectangle")
        # Include a modest boundary to avoid changing hair/skin around faces.
        l, t = max(0, int(a * W) - 6), max(0, int(b * H) - 6)
        r, bottom = min(W, int(np.ceil(c * W)) + 6), min(H, int(np.ceil(d * H)) + 6)
        lx, ly = max(l, x0) - x0, max(t, y0) - y0
        rx, ry = min(r, x0 + w) - x0, min(bottom, y0 + h) - y0
        if lx < rx and ly < ry:
            mask[ly:ry, lx:rx] = True
    return mask


def fuse_four_engine_details(
    source: Path,
    v2_reference: Path,
    candidates: dict[str, Path],
    output: Path,
    *,
    protected_regions: tuple[tuple[float, float, float, float], ...] = (),
    preserve_all_v2_faces: bool = False,
) -> dict:
    """Apply four previously validated model outputs to a distinct QA file.

    All four are mandatory. Never write over source, V2, or any candidate.
    If a GFPGAN/Studio AI face pass ran without mapped face rectangles, keep
    the complete V2 image as the output: an unknown face must not be altered.
    """
    if set(candidates) != set(ENGINES):
        raise ValueError("four independent AI candidates must complete before fusion")
    source, v2_reference, output = Path(source), Path(v2_reference), Path(output)
    inputs = [source, v2_reference, *(Path(candidates[name]) for name in ENGINES)]
    if any(output.resolve() == path.resolve() for path in inputs):
        raise ValueError("fusion may not overwrite source, V2 or AI candidates")
    if not isinstance(protected_regions, (tuple, list)):
        raise ValueError("face protection regions must be normalized rectangles")
    protected_regions = tuple(protected_regions)

    with ExitStack() as stack:
        base = stack.enter_context(Image.open(v2_reference))
        if base.format != "PNG" or base.mode not in ("RGB", "RGBA"):
            raise ValueError("V2 reference must be RGB/RGBA PNG")
        W, H = base.size
        with Image.open(source) as original:
            if (W, H) != (original.width * 2, original.height * 2):
                raise ValueError("four-engine fusion currently supports exact 2x only")
        metadata = {key: base.info[key] for key in ("icc_profile", "dpi") if key in base.info}
        for engine in ENGINES:
            validate_candidate(source, Path(candidates[engine]), (W, H))
        images = {}
        for engine in ENGINES:
            image = stack.enter_context(Image.open(candidates[engine]))
            if image.mode != base.mode or image.info.get("icc_profile") != metadata.get("icc_profile"):
                raise ValueError(engine + ": mode or ICC differs from accepted V2")
            # Normalized ICC is a necessity; DPI will be taken from V2.
            images[engine] = image
        # Validate all rectangles, including when face preservation is bypassed.
        _protected_mask(0, 0, 1, 1, (W, H), protected_regions)
        fused = Image.new(base.mode, (W, H))
        mean_delta_sum = 0.0
        edge_pixels = 0
        effective_contributions = {name: 0.0 for name in ENGINES}
        total_pixels = W * H
        # Working memory bounded by one region from each model.
        for y in range(0, H, TILE):
            for x in range(0, W, TILE):
                w, h = min(TILE, W - x), min(TILE, H - y)
                xx, yy = max(0, x - HALO), max(0, y - HALO)
                xx2, yy2 = min(W, x + w + HALO), min(H, y + h + HALO)
                box = (xx, yy, xx2, yy2)
                base_rgb = np.asarray(base.crop(box).convert("RGB"), dtype=np.float32)
                center = (slice(y - yy, y - yy + h), slice(x - xx, x - xx + w))
                base_c = base_rgb[center]
                base_hp = _gray_highpass(base.crop(box))[center]
                if preserve_all_v2_faces:
                    delta = np.zeros((h, w), dtype=np.float32)
                    edge_gate = np.zeros((h, w), dtype=bool)
                else:
                    diff = {}
                    for name in ENGINES:
                        hp = _gray_highpass(images[name].crop(box))[center]
                        diff[name] = np.clip(hp - base_hp, -12.0, 12.0)
                    # 3 trusted primary engines decide the detail direction.
                    core = sum(WEIGHTS[n] * diff[n] for n in WEIGHTS)
                    opinions = sum(np.sign(diff[n]) == np.sign(core) for n in WEIGHTS)
                    consensus = (opinions >= 2) & (np.abs(core) >= 0.9)
                    # Preserve flat fills and smooth colour ramps: only edges
                    # already present in V2 can receive a controlled detail lift.
                    edge_gate = consensus & (np.abs(base_hp) >= 2.5)
                    core_delta = 0.56 * core
                    # Anime4K is conditional edge-only detail; it never changes
                    # broad colours or gradients and cannot dominate 3 primaries.
                    anime = diff["anime4k"]
                    anime_agrees = (np.sign(anime) == np.sign(core)) & (np.abs(anime) <= 9.0)
                    anime_delta = ANIME4K_DETAIL_WEIGHT * np.where(anime_agrees, anime, 0.0)
                    delta = np.clip(core_delta + anime_delta, -MAX_DETAIL_CHANGE, MAX_DETAIL_CHANGE)
                    if base.mode == "RGBA":
                        alpha = np.asarray(base.crop((x, y, x+w, y+h)).getchannel("A"))
                        edge_gate &= alpha >= 250
                    edge_gate &= ~_protected_mask(x, y, w, h, (W, H), protected_regions)
                    delta = np.where(edge_gate, delta, 0.0)
                    for name in WEIGHTS:
                        effective_contributions[name] += float(
                            np.abs(diff[name][edge_gate] * WEIGHTS[name] * 0.56).sum()
                        )
                    effective_contributions["anime4k"] += float(
                        np.abs(anime_delta[edge_gate]).sum()
                    )
                # Shared luminance must fit every RGB channel; clipping channels
                # independently shifts hue at saturated print edges.
                upward = np.min(255.0 - base_c, axis=2)
                downward = np.min(base_c, axis=2)
                safe_delta = np.minimum(np.maximum(delta, -downward), upward)
                rgb = np.rint(base_c + safe_delta[..., None]).astype("uint8")
                if base.mode == "RGBA":
                    # Alpha is copied unchanged from V2; prevents fringe and
                    # satisfies PSD/AI transparent print workflow.
                    alpha = np.asarray(base.crop((x, y, x+w, y+h)).getchannel("A"), dtype="uint8")
                    output_array = np.dstack((rgb, alpha))
                else:
                    output_array = rgb
                fused.paste(Image.fromarray(output_array, mode=base.mode), (x, y))
                edge_pixels += int(edge_gate.sum())
                mean_delta_sum += float(np.abs(safe_delta).sum())
        output.parent.mkdir(parents=True, exist_ok=True)
        # Never write an incomplete PNG into the user-visible QA location.
        with NamedTemporaryFile(suffix=".png", prefix=".v211_fusion_", dir=output.parent, delete=False) as fh:
            temporary = Path(fh.name)
        try:
            fused.save(temporary, format="PNG", **metadata)
            with Image.open(temporary) as saved:
                saved.verify()
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)

    return {
        "fusion_implemented": True,
        "fusion_mode": "four_models_edge_luminance_guarded_v2_colour",
        "all_four_engine_candidates_consumed": True,
        "primary_engines": list(WEIGHTS),
        "anime4k_role": "conditional_edge_detail_only",
        "v2_colour_and_alpha_preserved": True,
        "v2_file_not_modified": True,
        "protected_faces_preserved": bool(protected_regions) or preserve_all_v2_faces,
        "preserve_all_v2_faces": preserve_all_v2_faces,
        "edge_pixels_modified_or_considered": edge_pixels,
        "mean_abs_detail_delta": round(mean_delta_sum / max(1, total_pixels), 5),
        "engine_detail_contribution_mean_abs": {
            name: round(value / max(1, total_pixels), 6)
            for name, value in effective_contributions.items()
        },
        "output": str(output),
        "quality_certified": False,
        "experimental_preview_only": True,
    }
