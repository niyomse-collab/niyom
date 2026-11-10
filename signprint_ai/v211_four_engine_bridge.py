"""Opt-in V2.1.1 four-engine research hook, isolated from accepted V2 output.

Each native executable performs one 2x pass on a private seed made at half of
the accepted V2 target canvas. The current runner accepts exact isotropic 2x
or 4x source geometry for small jobs; 4x uses a half-target seed followed by
one native 2x pass, not native 4x inference or a multi-pass workflow. Jobs
above 18 MP accept exact isotropic 2x, 4x or 8x PNG source-to-V2 geometry
through disk-backed tiles. Each route executes one native 2x pass on a
half-target seed; large 4x uses a 2x seed and large 8x uses a 4x seed. Neither
is native 4x/8x or multi-pass inference. 3x, custom, anisotropic and non-PNG
jobs remain unsupported and fail before native inference. Small jobs require a seed of at least 2x2;
disk-backed large jobs require at least 64x64. Pixel/row/disk limits fail closed.

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

_ENGINE_NAMES = ("real_esrgan", "waifu2x", "real_cugan", "anime4k")


def _all_four_runtime_devices_verified(result: dict) -> bool:
    """Require live per-process proof for every native engine before QA export."""
    if not isinstance(result, dict) or result.get("runtime_device_use_verified") is not True:
        return False
    per_engine = result.get("per_engine_runtime_device_use_verified")
    return (
        isinstance(per_engine, dict)
        and set(per_engine) == set(_ENGINE_NAMES)
        and all(per_engine.get(name) is True for name in _ENGINE_NAMES)
    )


def _gpu_runtime_unverified_result(result: dict) -> dict:
    """Return a fail-closed status without exposing or retaining a QA sidecar."""
    per_engine = result.get("per_engine_runtime_device_use_verified")
    if not isinstance(per_engine, dict):
        per_engine = {}
    binding = result.get("device_binding")
    binding = dict(binding) if isinstance(binding, dict) else {}
    binding["runtime_device_use_verified"] = False
    binding["per_engine_runtime_device_use_verified"] = per_engine
    return {
        "status": "gpu_runtime_unverified",
        "reason": "all_four_native_processes_must_be_verified_on_the_selected_gtx_1660_ti",
        "completed_engine_count": result.get("completed_engine_count", 0),
        "runtime_device_use_verified": False,
        "per_engine_runtime_device_use_verified": per_engine,
        "device_binding": binding,
        "v2_output_preserved": True,
        "quality_certified": False,
    }

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


def _prelaunch_vram_check(engine: str) -> dict:
    """Recheck GTX 1660 Ti free VRAM immediately before each native process."""
    from tools.v211_gpu_device_binding import validate_free_vram_report
    from tools.v211_shop_gpu_diagnostic import probe_nvidia_smi_memory

    try:
        return validate_free_vram_report(probe_nvidia_smi_memory())
    except GPUDeviceBindingError as exc:
        raise GPUDeviceBindingError(
            str(engine) + ": per-process free-VRAM check failed"
        ) from exc



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
            source_icc = source_image.info.get("icc_profile")
            # Missing and embedded profiles are different colour contracts.
            # Do not attach the V2 ICC to an untagged source seed: that would
            # silently reinterpret customer RGB values during auxiliary fusion.
            if source_icc != metadata.get("icc_profile"):
                raise ValueError(
                    "source ICC differs in presence or content from the accepted V2 profile; "
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
        # Native CLIs are fixed at 2x. Build their input from half of the
        # exact accepted V2 canvas rather than restricting the user's original
        # source-to-print scale. This supports custom/anisotropic dimensions
        # while keeping the V2 raster as the authoritative colour/alpha base.
        padded_target_size = (
            target_size[0] + target_size[0] % 2,
            target_size[1] + target_size[1] % 2,
        )
        seed_size = (
            padded_target_size[0] // 2,
            padded_target_size[1] // 2,
        )
        large_job = max(
            source_size[0] * source_size[1],
            target_size[0] * target_size[1],
        ) > _AUXILIARY_MAX_PIXELS
        # Reject undersized native seeds first, preserving the explicit
        # diagnostic for tiny jobs before checking the original print scale.
        minimum_seed_dimension = 64 if large_job else 2
        if min(seed_size) < minimum_seed_dimension:
            return {
                "status": "unsupported_target_geometry",
                "reason": (
                    "half_target_seed_must_be_at_least_64x64_for_disk_tiles"
                    if large_job else
                    "half_target_seed_must_be_at_least_2x2"
                ),
                "v2_output_preserved": True,
                "quality_certified": False,
            }
        source_to_target_scale = next(
            (
                scale for scale in (2, 4, 8)
                if target_size == (source_size[0] * scale, source_size[1] * scale)
            ),
            None,
        )
        # The runner sees only a half-target seed, so its own 2x preflight
        # cannot detect an unsupported original-to-print scale such as 3x.
        # Reject those geometries here, before GPU binding or any native CLI.
        if large_job and (
            source_to_target_scale not in (2, 4, 8)
            or original.suffix.lower() != ".png"
            or baseline.suffix.lower() != ".png"
        ):
            return {
                "status": "unsupported_target_geometry",
                "reason": "large_auxiliary_jobs_require_exact_2x_4x_or_8x_png_geometry",
                "v2_output_preserved": True,
                "quality_certified": False,
            }
        if source_to_target_scale is None or (
            not large_job and source_to_target_scale not in (2, 4)
        ):
            return {
                "status": "unsupported_target_geometry",
                "reason": "source_to_v2_geometry_must_be_exact_isotropic_2x_or_4x",
                "v2_output_preserved": True,
                "quality_certified": False,
            }

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
                    real_engines=True,
                    v2_reference=reference,
                    pre_launch_check=_prelaunch_vram_check,
                    **run_options,
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
            fusion_ready = bool(
                fusion.get("fusion_implemented")
                and fusion.get("all_four_engine_pixels_contributed")
                and fusion.get("output")
            )
            if result.get("fusion_block_reason") == "gpu_runtime_unverified" or (
                fusion_ready and not _all_four_runtime_devices_verified(result)
            ):
                # The evidence directory is explicitly local-only; discard the
                # candidate images when GPU use cannot be tied to all four PIDs.
                shutil.rmtree(output_dir, ignore_errors=True)
                return _gpu_runtime_unverified_result(result)
            private_output = None
            if (fusion.get("fusion_implemented")
                    and fusion.get("all_four_engine_pixels_contributed")
                    and fusion.get("output")):
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
                fusion_ready = bool(
                    fusion.get("fusion_implemented")
                    and fusion.get("all_four_engine_pixels_contributed")
                    and fusion.get("output")
                )
                if result.get("fusion_block_reason") == "gpu_runtime_unverified" or (
                    fusion_ready and not _all_four_runtime_devices_verified(result)
                ):
                    return _gpu_runtime_unverified_result(result)
                if (fusion.get("fusion_implemented")
                    and fusion.get("all_four_engine_pixels_contributed")
                    and fusion.get("output")):
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
        # A priority preview created inside the default TemporaryDirectory has
        # already been deleted here. Do not report it as "ready" unless the
        # private evidence directory actually retains the file for inspection.
        priority_preview_path = None
        if evidence_root and selection is not None:
            preview_output = preview.get("output")
            if preview_output:
                candidate_preview = Path(preview_output)
                if candidate_preview.is_file():
                    priority_preview_path = str(candidate_preview)
        source_w, source_h = source_size
        target_w, target_h = target_size
        runtime_verified = _all_four_runtime_devices_verified(result)
        per_engine_runtime = result.get("per_engine_runtime_device_use_verified")
        if not isinstance(per_engine_runtime, dict):
            per_engine_runtime = {}
        device_binding = result.get("device_binding")
        device_binding = dict(device_binding) if isinstance(device_binding, dict) else {}
        device_binding["runtime_device_use_verified"] = runtime_verified
        device_binding["per_engine_runtime_device_use_verified"] = per_engine_runtime
        return {
            "status": (
                "four_engine_fusion_preview_ready"
                if fusion.get("fusion_implemented") and fusion.get("all_four_engine_pixels_contributed")
                else "four_engine_fusion_contribution_incomplete"
                if fusion.get("fusion_implemented")
                else "three_engine_priority_preview_ready"
                if priority_preview_path is not None
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
            "priority_preview_path": priority_preview_path,
            "anime4k_optional_for_priority_preview": True,
            "failures": result.get("failures", {}),
            "fusion_implemented": bool(fusion.get("fusion_implemented")),
            "all_four_engine_pixels_contributed": bool(fusion.get("all_four_engine_pixels_contributed")),
            "engine_pixel_effect_pixels": fusion.get("engine_pixel_effect_pixels"),
            "engine_pixel_effect_verified": fusion.get("engine_pixel_effect_verified"),
            "runtime_device_use_verified": runtime_verified,
            "per_engine_runtime_device_use_verified": per_engine_runtime,
            "device_binding": device_binding,
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
