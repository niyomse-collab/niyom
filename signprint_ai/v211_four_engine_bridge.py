"""Opt-in V2.1.1 four-engine research hook, isolated from accepted V2 output.

The native executables are fixed 2x upscalers. For arbitrary V2 raster dimensions,
the bridge creates a half-target seed from the original source, edge-pads odd
V2 dimensions, and asks each native engine for one 2x pass. This makes custom,
4x and 8x *target dimensions* eligible for a candidate preview; it is NOT native
4x/8x inference or a multi-pass super-resolution claim.

No candidate is silently used as the printed deliverable: quality approval is a
separate release gate.
"""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import tempfile
import shutil
from uuid import uuid4
from typing import Callable

from PIL import Image, ImageOps
from .v211_large_image_bridge import (
    inspect_image,
    prepare_native_2x_inputs_streamed,
    save_cropped_png_streamed,
)
from tools.v211_gpu_device_binding import GPUDeviceBindingError, write_bound_manifest

_LOG = logging.getLogger(__name__)
_FLAG = "NIYOMSIL_V211_FOUR_AI"
_MANIFEST = "NIYOMSIL_V211_FOUR_AI_MANIFEST"
_EVIDENCE = "NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR"

# This is an auxiliary-engine budget, NOT a V2 resize/export pixel limit.
AUXILIARY_MAX_PIXELS = 18_000_000
_AUXILIARY_MAX_PIXELS = AUXILIARY_MAX_PIXELS
_SOURCE_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
_V2_RASTER_FORMATS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _metadata(image: Image.Image) -> dict:
    return {key: image.info[key] for key in ("icc_profile", "dpi") if key in image.info}


def _prepare_runtime_bound_manifest(manifest_path: Path, work_dir: Path) -> tuple[Path, dict]:
    """Bind every native CLI to the uniquely detected GTX 1660 Ti for this run.

    The installed manifest is read-only. A private temporary copy receives
    explicit NCNN -g and Anime4KCPP -p/-d values after fresh local inventory.
    """
    from tools.v211_shop_gpu_diagnostic import probe_gpu, probe_anime4k_backend

    bound_path = Path(work_dir) / "manifest.runtime-bound.json"
    selection = write_bound_manifest(
        Path(manifest_path),
        bound_path,
        probe_gpu(),
        probe_anime4k_backend(Path(manifest_path)),
    )
    return bound_path, selection


def _oriented_size(image: Image.Image) -> tuple[int, int]:
    """Read EXIF-oriented dimensions from the header without decoding pixels."""
    width, height = image.size
    try:
        orientation = image.getexif().get(274)
    except (OSError, TypeError, ValueError):
        orientation = None
    return (height, width) if orientation in (5, 6, 7, 8) else (width, height)


def _edge_pad_even(image: Image.Image) -> Image.Image:
    """Repeat the last row/column so a fixed 2x engine lands on an even target."""
    width, height = image.size
    padded_width, padded_height = width + (width % 2), height + (height % 2)
    if (padded_width, padded_height) == (width, height):
        return image.copy()
    padded = Image.new(image.mode, (padded_width, padded_height))
    padded.paste(image, (0, 0))
    if padded_width != width:
        padded.paste(image.crop((width - 1, 0, width, height)), (width, 0))
    if padded_height != height:
        padded.paste(image.crop((0, height - 1, width, height)), (0, height))
    if padded_width != width and padded_height != height:
        padded.putpixel((width, height), image.getpixel((width - 1, height - 1)))
    return padded


def _prepare_native_2x_inputs(
    source: Path,
    baseline: Path,
    work_dir: Path,
    *,
    resize_mode: str = "stretch",
) -> tuple[Path, Path, tuple[int, int], tuple[int, int], tuple[int, int], dict]:
    """Create a private half-target seed and a PNG V2 reference for the 2x CLIs."""
    if resize_mode not in ("fit", "stretch"):
        raise ValueError("resize_mode must be 'fit' or 'stretch'")

    with Image.open(baseline) as v2_image:
        if v2_image.mode not in ("RGB", "RGBA"):
            raise ValueError("V2 raster must be RGB or RGBA; CMYK remains V2-only")
        target_size = v2_image.size
        padded_size = (target_size[0] + target_size[0] % 2,
                       target_size[1] + target_size[1] % 2)
        # Reject oversized targets from header dimensions BEFORE _edge_pad_even
        # copies or decodes the full raster into RAM.
        if padded_size[0] * padded_size[1] > _AUXILIARY_MAX_PIXELS:
            raise ValueError("auxiliary_image_too_large")
        metadata = _metadata(v2_image)
        seed_size = (padded_size[0] // 2, padded_size[1] // 2)
        if min(seed_size) < 2:
            raise ValueError("auxiliary_target_too_small")

        with Image.open(source) as source_image:
            source_size = _oriented_size(source_image)
            # Reject a huge source before EXIF transpose/convert can allocate
            # a full decoded copy. V2 itself remains free to process larger
            # files through its disk-tile pipeline.
            if source_size[0] * source_size[1] > _AUXILIARY_MAX_PIXELS:
                raise ValueError("auxiliary_source_too_large")
            if source_image.mode not in ("RGB", "RGBA"):
                raise ValueError("source must be RGB or RGBA for four-engine research")
            if source_image.info.get("icc_profile") != metadata.get("icc_profile"):
                raise ValueError(
                    "source and accepted V2 ICC profiles differ; "
                    "keep the approved V2 output without auxiliary fusion"
                )

            # No work directory or reference file is created until geometry,
            # colour mode and source/V2 ICC compatibility have passed.
            padded_v2 = _edge_pad_even(v2_image)
            work_dir.mkdir(parents=True, exist_ok=True)
            reference_path = work_dir / "v2_reference_native_2x.png"
            seed_path = work_dir / "native_2x_seed.png"
            padded_v2.save(reference_path, format="PNG", **metadata)

            oriented = ImageOps.exif_transpose(source_image)
            converted = oriented.convert(padded_v2.mode)
            if resize_mode == "stretch":
                seed = converted.resize(seed_size, resample=Image.Resampling.LANCZOS)
            else:
                # The native seed must use the same geometry as the accepted
                # V2 raster. Stretching a wide source into a square half-target
                # would move every edge before the engines see it, then fuse
                # those displaced details back onto the correctly letterboxed V2.
                factor = min(seed_size[0] / converted.width, seed_size[1] / converted.height)
                contained_size = (
                    max(1, min(seed_size[0], round(converted.width * factor))),
                    max(1, min(seed_size[1], round(converted.height * factor))),
                )
                contained = converted.resize(contained_size, resample=Image.Resampling.LANCZOS)
                background = padded_v2.getpixel((0, 0))
                seed = Image.new(padded_v2.mode, seed_size, background)
                seed.paste(
                    contained,
                    ((seed_size[0] - contained_size[0]) // 2,
                     (seed_size[1] - contained_size[1]) // 2),
                )
            # The accepted V2 alpha is authoritative, including when the
            # original source is RGB or an external model invents transparency.
            if padded_v2.mode == "RGBA":
                seed.putalpha(
                    padded_v2.getchannel("A").resize(
                        seed_size, resample=Image.Resampling.LANCZOS
                    )
                )
            seed.save(seed_path, format="PNG", **metadata)

    return seed_path, reference_path, target_size, padded_size, source_size, metadata

def _save_cropped_png(
    candidate: Path,
    destination: Path,
    *,
    target_size: tuple[int, int],
    padded_size: tuple[int, int],
    mode: str,
    metadata: dict,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """Publish a cropped QA PNG exclusively; large canvases stay disk-backed."""
    if padded_size[0] * padded_size[1] > _AUXILIARY_MAX_PIXELS:
        save_cropped_png_streamed(
            candidate,
            destination,
            target_size=target_size,
            padded_size=padded_size,
            mode=mode,
            metadata=metadata,
            cancel_check=cancel_check,
        )
        return
    with Image.open(candidate) as image:
        if image.size != padded_size or image.mode != mode:
            raise ValueError("four-engine candidate dimensions or mode mismatch")
        cropped = image.crop((0, 0, target_size[0], target_size[1]))
        with tempfile.NamedTemporaryFile(
            suffix=".png", prefix=".v211_qa_", dir=destination.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            cropped.save(temporary, format="PNG", **metadata)
            with temporary.open("rb") as source_stream, destination.open("xb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream)
        finally:
            temporary.unlink(missing_ok=True)


def maybe_run_four_engine_assist(
    source: str | Path,
    v2_output: str | Path,
    *,
    use_ai: bool = True,
    cancel: Callable[[], bool] | None = None,
    protected_regions: tuple = (),
    preserve_all_v2_faces: bool = False,
    progress: Callable[[int, str], None] | None = None,
    resize_mode: str = "stretch",
) -> dict:
    """Run four verified native 2x engines after V2 safely saves.

    A failure is reported but NEVER modifies the V2 file, its ICC/DPI/alpha,
    GFPGAN face result, or UI controls. The sidecar path is local-only.
    """
    if not use_ai or os.environ.get(_FLAG) == "0":
        return {"status": "disabled", "v2_output_preserved": True}
    if cancel and cancel():
        return {"status": "cancelled", "v2_output_preserved": True}
    # If GFPGAN/Studio AI ran but the adapter cannot map its face ROIs onto
    # the final V2 canvas, fusion is contractually required to preserve the
    # ENTIRE V2 raster unchanged. Running four native processes in that case
    # can never affect the preview, so skip them before manifest/device setup.
    if preserve_all_v2_faces:
        return {
            "status": "face_protection_v2_only",
            "reason": "unmapped_face_regions",
            "v2_output_preserved": True,
            "quality_certified": False,
        }

    original = Path(source)
    baseline = Path(v2_output)
    manifest_name = os.environ.get(_MANIFEST, "").strip()
    # The experimental V2.1.1 build uses four models automatically after
    # they have been provisioned once to a private directory. Stable V2 never
    # imports this bridge and no per-model UI switches are introduced.
    if not manifest_name:
        local_appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        available = local_appdata / "NiyomSilp" / "V211-FourAI-QA" / "manifest.json"
        if available.is_file():
            manifest_name = str(available)
    if not manifest_name:
        return {"status": "models_not_installed", "v2_output_preserved": True}
    if baseline.suffix.lower() not in _V2_RASTER_FORMATS:
        return {"status": "unsupported_output_format", "v2_output_preserved": True}
    if original.suffix.lower() not in _SOURCE_FORMATS:
        return {"status": "unsupported_source_format", "v2_output_preserved": True}

    output_dir: Path | None = None
    persistent_output_dir = False
    sidecar: Path | None = None
    try:
        source_size, source_mode, _source_metadata = inspect_image(
            original, orient=True
        )
        target_size, target_mode, _target_metadata = inspect_image(baseline)
        if target_mode not in ("RGB", "RGBA"):
            return {"status": "unsupported_colour_mode", "v2_output_preserved": True}
        if source_mode not in ("RGB", "RGBA"):
            return {"status": "unsupported_source_mode", "v2_output_preserved": True}
        large_job = max(
            source_size[0] * source_size[1],
            target_size[0] * target_size[1],
        ) > _AUXILIARY_MAX_PIXELS

        from tools.v211_four_engine_run import run

        evidence_root = os.environ.get(_EVIDENCE, "").strip()
        guard_options = {}
        if protected_regions or preserve_all_v2_faces:
            guard_options = {
                "protected_regions": protected_regions,
                "preserve_all_v2_faces": preserve_all_v2_faces,
            }
        run_options = {**guard_options}
        if cancel is not None:
            run_options["cancel"] = cancel
        if progress is not None:
            run_options["progress_callback"] = progress

        def execute(work_dir: Path):
            if cancel and cancel():
                raise InterruptedError("Processing stopped by user")
            prepare_inputs = (
                prepare_native_2x_inputs_streamed if large_job
                else _prepare_native_2x_inputs
            )
            if large_job:
                prepared = prepare_inputs(
                    original,
                    baseline,
                    work_dir,
                    resize_mode=resize_mode,
                    cancel_check=cancel,
                    progress_callback=progress,
                )
            else:
                prepared = prepare_inputs(
                    original, baseline, work_dir, resize_mode=resize_mode
                )
            seed, reference, target_size, padded_size, source_size, metadata = prepared
            if cancel and cancel():
                raise InterruptedError("Processing stopped by user")
            bound_manifest, device_binding = _prepare_runtime_bound_manifest(
                Path(manifest_name), work_dir
            )
            try:
                result = run(
                    seed, work_dir, bound_manifest, padded_size,
                    real_engines=True, v2_reference=reference, **run_options,
                )
            finally:
                # The persistent installation manifest remains untouched and
                # no temporary absolute paths are retained with private evidence.
                bound_manifest.unlink(missing_ok=True)
            result["device_binding"] = device_binding
            return result, target_size, padded_size, source_size, metadata

        if evidence_root:
            root = Path(evidence_root).expanduser()
            root.mkdir(parents=True, exist_ok=True)
            output_dir = root / ("v211-" + uuid4().hex)
            output_dir.mkdir(mode=0o700)
            persistent_output_dir = True
            result, target_size, padded_size, source_size, metadata = execute(output_dir)
            fusion = result.get("four_engine_fusion") or {}
            private_output = None
            if fusion.get("fusion_implemented") and fusion.get("output"):
                cropped = output_dir / "four_engine_fused_preview_cropped.png"
                _save_cropped_png(
                    Path(fusion["output"]), cropped,
                    target_size=target_size, padded_size=padded_size,
                    mode=target_mode, metadata=metadata, cancel_check=cancel,
                )
                fusion["output"] = str(cropped)
                private_output = str(cropped)
        else:
            # Intermediate candidates remain in a private temporary directory.
            # Retain only the QA PNG beside V2; the approved raster stays intact.
            private_output = None
            with tempfile.TemporaryDirectory(prefix="niyomsil-v211-") as temporary:
                output_dir = Path(temporary)
                result, target_size, padded_size, source_size, metadata = execute(output_dir)
                if cancel and cancel():
                    raise InterruptedError("Processing stopped by user")
                fusion = result.get("four_engine_fusion") or {}
                if fusion.get("fusion_implemented") and fusion.get("output"):
                    name = baseline.stem + ".V211-4AI-QA-" + uuid4().hex[:8] + ".png"
                    sidecar = baseline.with_name(name)
                    _save_cropped_png(
                        Path(fusion["output"]), sidecar,
                        target_size=target_size, padded_size=padded_size,
                        mode=target_mode, metadata=metadata, cancel_check=cancel,
                    )
                    fusion["output"] = str(sidecar)
                    private_output = str(sidecar)

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        fusion = result.get("four_engine_fusion") or {}
        preview = result.get("three_engine_priority_preview") or {}
        selection = preview.get("selected")
        source_w, source_h = source_size
        target_w, target_h = target_size
        return {
            "status": (
                "four_engine_fusion_preview_ready"
                if fusion.get("fusion_implemented") and fusion.get("all_four_engine_pixels_contributed")
                else "four_engine_fusion_contribution_incomplete"
                if fusion.get("fusion_implemented")
                else "three_engine_priority_preview_ready"
                if selection is not None
                else "candidate_research_complete"
                if result.get("ready_for_fusion_research")
                else "incomplete_four_engine_candidates"
            ),
            "completed_engine_count": result.get("completed_engine_count", 0),
            "four_engine_fusion_output": private_output,
            "four_engine_fusion_details": {
                "mean_abs_detail_delta": fusion.get("mean_abs_detail_delta"),
                "engine_detail_contribution_mean_abs": fusion.get("engine_detail_contribution_mean_abs"),
                "protected_faces_preserved": fusion.get("protected_faces_preserved"),
                "native_engine_scale": 2,
                "engine_input_size": [padded_size[0] // 2, padded_size[1] // 2],
                "requested_output_size": list(target_size),
                "requested_scale_from_source": [
                    round(target_w / source_w, 4), round(target_h / source_h, 4)
                ],
                "scale_policy": "native_2x_on_half_target_seed",
                "resize_mode": resize_mode,
            } if fusion else None,
            "priority_preview_selected": selection,
            "priority_preview_path": (
                preview.get("output") if evidence_root and selection is not None
                else None
            ),
            "anime4k_optional_for_priority_preview": True,
            "failures": result.get("failures", {}),
            "fusion_implemented": bool(fusion.get("fusion_implemented")),
            "all_four_engine_pixels_contributed": bool(fusion.get("all_four_engine_pixels_contributed")),
            "engine_pixel_effect_pixels": fusion.get("engine_pixel_effect_pixels"),
            "engine_pixel_effect_verified": fusion.get("engine_pixel_effect_verified"),
            "device_binding": result.get("device_binding"),
            "quality_certified": False,
            "v2_output_preserved": True,
        }
    except InterruptedError:
        if persistent_output_dir and output_dir is not None:
            shutil.rmtree(output_dir, ignore_errors=True)
        if sidecar is not None:
            sidecar.unlink(missing_ok=True)
        return {"status": "cancelled", "v2_output_preserved": True}
    except GPUDeviceBindingError as exc:
        if persistent_output_dir and output_dir is not None:
            shutil.rmtree(output_dir, ignore_errors=True)
        if sidecar is not None:
            sidecar.unlink(missing_ok=True)
        _LOG.warning(
            "Optional V2.1.1 four-engine GPU binding blocked (%s)",
            type(exc).__name__,
        )
        return {
            "status": "gpu_binding_unverified",
            "reason": "GTX 1660 Ti GPU selection was ambiguous or unavailable",
            "error_type": type(exc).__name__,
            "v2_output_preserved": True,
            "quality_certified": False,
        }
    except Exception as exc:
        if persistent_output_dir and output_dir is not None:
            shutil.rmtree(output_dir, ignore_errors=True)
        if sidecar is not None:
            sidecar.unlink(missing_ok=True)
        # Native exception messages can include customer filenames, LOCALAPPDATA
        # locations, or command details. Keep diagnostics useful without logging
        # or returning the sensitive message.
        _LOG.warning(
            "Optional V2.1.1 four-engine candidate run failed (%s)",
            type(exc).__name__,
        )
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error_class": "processing_failed",
            "v2_output_preserved": True,
        }
