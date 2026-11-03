"""Opt-in V2.1.1 four-engine research hook, isolated from accepted V2 output.

When enabled, the four verified external executables receive the ORIGINAL source
and a trusted V2 output at one target size. No candidate is silently used as
the printed deliverable: quality approval is a separate release gate.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile
from typing import Callable

from PIL import Image

_LOG = logging.getLogger(__name__)
_FLAG = "NIYOMSIL_V211_FOUR_AI"
_MANIFEST = "NIYOMSIL_V211_FOUR_AI_MANIFEST"
_EVIDENCE = "NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR"

# This is an auxiliary-engine budget, NOT a V2 resize/export pixel limit.
_AUXILIARY_MAX_PIXELS = 18_000_000


def maybe_run_four_engine_assist(
    source: str | Path,
    v2_output: str | Path,
    *,
    use_ai: bool = True,
    cancel: Callable[[], bool] | None = None,
) -> dict:
    """Run an optional four-engine candidate comparison after V2 safely saves.

    A failure is reported but NEVER modifies the V2 file, its ICC/DPI/alpha,
    GFPGAN face result, or UI controls. The sidecar path is local-only.
    Real executable+checkpoint hashes are validated by the manifest loader.
    """
    if not use_ai or os.environ.get(_FLAG) != "1":
        return {"status": "disabled", "v2_output_preserved": True}
    if cancel and cancel():
        return {"status": "cancelled", "v2_output_preserved": True}

    original = Path(source)
    baseline = Path(v2_output)
    manifest_name = os.environ.get(_MANIFEST, "").strip()
    if not manifest_name:
        return {"status": "missing_manifest", "v2_output_preserved": True}
    if baseline.suffix.lower() != ".png":
        return {"status": "unsupported_output_format", "v2_output_preserved": True}

    try:
        with Image.open(baseline) as image:
            if image.mode not in ("RGB", "RGBA"):
                return {"status": "unsupported_colour_mode", "v2_output_preserved": True}
            target_size = image.size
            if target_size[0] * target_size[1] > _AUXILIARY_MAX_PIXELS:
                return {"status": "auxiliary_image_too_large", "v2_output_preserved": True}

        # Current NCNN/Anime4KCPP adapters are deliberately configured for
        # EXACT 2x. Do not start four expensive external processes for V2
        # resize/print modes such as 1x, 3x, 4x, 8x, TIFF, or PDF.
        # V2 retains its original large-format route unaffected.
        if original.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            return {"status": "unsupported_source_format", "v2_output_preserved": True}
        with Image.open(original) as source_image:
            if source_image.mode not in ("RGB", "RGBA"):
                return {"status": "unsupported_source_mode", "v2_output_preserved": True}
            if target_size != (source_image.width * 2, source_image.height * 2):
                return {"status": "auxiliary_engine_scale_mismatch", "v2_output_preserved": True}

        # Import only after the explicit opt-in. Default V2 never needs optional
        # engine packages and stays unchanged when this feature is unavailable.
        from tools.v211_four_engine_run import run

        evidence_root = os.environ.get(_EVIDENCE, "").strip()
        if evidence_root:
            # Caller explicitly opted into retaining private customer-image
            # candidates locally for a human A/B comparison.
            root = Path(evidence_root).expanduser()
            root.mkdir(parents=True, exist_ok=True)
            from uuid import uuid4
            output_dir = root / ("v211-" + uuid4().hex)
            output_dir.mkdir(mode=0o700)
            result = run(original, output_dir, Path(manifest_name), target_size,
                         real_engines=True, v2_reference=baseline)
        else:
            # Do not silently retain customer artwork in permanent diagnostics.
            with tempfile.TemporaryDirectory(prefix="niyomsil-v211-") as temporary:
                result = run(original, Path(temporary), Path(manifest_name),
                             target_size, real_engines=True, v2_reference=baseline)

        preview = result.get("three_engine_priority_preview") or {}
        selection = preview.get("selected")
        return {
            "status": (
                "candidate_research_complete"
                if result.get("ready_for_fusion_research")
                else "three_engine_priority_preview_ready"
                if selection is not None
                else "incomplete_four_engine_candidates"
            ),
            "completed_engine_count": result.get("completed_engine_count", 0),
            "priority_preview_selected": selection,
            # Expose only retained local outputs, never a deleted temp path.
            "priority_preview_path": (
                preview.get("output") if evidence_root and selection is not None
                else None
            ),
            "anime4k_optional_for_priority_preview": True,
            "failures": result.get("failures", {}),
            "fusion_implemented": False,
            "quality_certified": False,
            "v2_output_preserved": True,
        }
    except Exception as exc:
        # A sidecar failure cannot fail the accepted V2 enhancement job.
        _LOG.warning("Optional V2.1.1 four-engine candidate run failed: %s", exc)
        return {
            "status": "error",
            "error": type(exc).__name__ + ": " + str(exc),
            "v2_output_preserved": True,
        }
