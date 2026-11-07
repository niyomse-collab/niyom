"""Disk-backed 2x native-engine tile orchestration for V2.1.1 research.

This module is deliberately a runner-level prototype. It invokes one existing
native processor at a time on bounded PNG tiles, checks overlapping predictions
for gross disagreement, stitches only each tile's non-overlapping core to a
disk-backed raster, and takes RGBA alpha from the accepted V2 reference.

It does not certify visual quality, GPU adapter use, or print readiness. The
application bridge remains fail-closed until its own large-image seed creation
and install/QA path are converted to the same bounded workflow.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Callable, Mapping
import shutil

import numpy as np
from PIL import Image

from tools.v211_four_engine_coordinator import Candidate, ENGINES
from tools.v211_four_engine_fusion import (
    MAX_STREAMED_PIXELS,
    MAX_STREAMED_ROW_BYTES,
    _open_fusion_image,
    _write_streamed_png,
)

DEFAULT_TILE_SIZE = 512
DEFAULT_OVERLAP = 32
SEAM_MAX_CHANNEL_DELTA = 48
SEAM_MEAN_CHANNEL_DELTA = 6.0
DISK_RESERVE_BYTES = 64 * 1024 * 1024


class DiskReserveError(RuntimeError):
    """Raised when the complete four-engine workspace can no longer be reserved."""


def _required_disk_bytes(
    raw_bytes: int,
    *,
    remaining_candidates: int = len(ENGINES),
    completed_candidate_bytes: int = 0,
) -> int:
    """Reserve remaining candidates, completed files, staging and fusion workspaces.

    Earlier candidate PNGs remain on disk until fusion. Count their actual byte
    sizes while reserving a full raw-raster equivalent for each engine yet to run.
    """
    if not isinstance(raw_bytes, int) or raw_bytes < 1:
        raise ValueError("raw raster byte count must be a positive integer")
    if (not isinstance(remaining_candidates, int)
            or not 1 <= remaining_candidates <= len(ENGINES)):
        raise ValueError("remaining candidate count is outside the four-engine range")
    if not isinstance(completed_candidate_bytes, int) or completed_candidate_bytes < 0:
        raise ValueError("completed candidate byte count must be non-negative")
    return (
        raw_bytes * (remaining_candidates + 3)
        + completed_candidate_bytes
        + DISK_RESERVE_BYTES
    )


def _open_vips_region(path: Path, expected_size: tuple[int, int], mode: str):
    """Return a random-access libvips image and Region without full decoding."""
    try:
        import pyvips
    except ImportError as exc:
        raise RuntimeError("pyvips is required for disk-backed native tile inference") from exc
    image = pyvips.Image.new_from_file(
        str(path), access="random", fail_on="error", unlimited=True
    )
    expected_bands = 4 if mode == "RGBA" else 3
    if (image.width, image.height) != expected_size:
        raise ValueError("libvips dimensions differ from the PNG header")
    if image.format != "uchar" or image.bands != expected_bands:
        raise ValueError("tiled native inference requires 8-bit RGB/RGBA PNG")
    return image, pyvips.Region.new(image)



def _expand_interval(start: int, end: int, limit: int, halo: int) -> tuple[int, int]:
    """Keep edge tiles large enough for native kernels while retaining the core."""
    left = max(0, start - halo)
    right = min(limit, end + halo)
    minimum = 64
    if right - left < minimum:
        if left == 0:
            right = min(limit, minimum)
        elif right == limit:
            left = max(0, limit - minimum)
        else:
            missing = minimum - (right - left)
            take_left = min(left, missing // 2)
            left -= take_left
            right = min(limit, right + missing - take_left)
            if right - left < minimum:
                left = max(0, right - minimum)
    if right - left < minimum:
        raise ValueError("native edge tile is smaller than the minimum supported kernel size")
    return left, right

def _read_region(region, mode: str, box: tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    pixels = region.fetch(left, top, width, height)
    channels = 4 if mode == "RGBA" else 3
    if len(pixels) != width * height * channels:
        raise ValueError("libvips returned an incomplete native input tile")
    return Image.frombytes(mode, (width, height), pixels)


def _dpi_matches(actual, expected) -> bool:
    if expected is None:
        return actual is None
    if actual is None or len(actual) < 2 or len(expected) < 2:
        return False
    try:
        return all(abs(float(actual[i]) - float(expected[i])) <= 0.1 for i in (0, 1))
    except (TypeError, ValueError):
        return False


def _validate_tile_output(
    path: Path,
    expected_size: tuple[int, int],
    source_mode: str,
    source_metadata: dict,
) -> None:
    with Image.open(path) as image:
        if image.size != expected_size:
            raise ValueError("native tile output is not exactly 2x the input tile")
        if source_mode == "RGB" and image.mode != "RGB":
            raise ValueError("RGB native tile unexpectedly introduced transparency")
        if source_mode == "RGBA" and image.mode not in ("RGB", "RGBA"):
            raise ValueError("RGBA native tile must return RGB or RGBA pixels")
        if image.info.get("icc_profile") != source_metadata.get("icc_profile"):
            raise ValueError("native tile ICC differs from the source")
        if not _dpi_matches(image.info.get("dpi"), source_metadata.get("dpi")):
            raise ValueError("native tile DPI differs from the source")


def _compare_overlap(
    left_path: Path,
    left_rect: tuple[int, int, int, int],
    right_path: Path,
    right_rect: tuple[int, int, int, int],
    *,
    axis: str,
    boundary: int,
    overlap: int,
) -> tuple[int, float]:
    """Compare the same global pixels predicted by adjacent tiles."""
    ax0, ay0, ax1, ay1 = left_rect
    bx0, by0, bx1, by1 = right_rect
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        raise ValueError("adjacent native tiles do not overlap")
    half = max(1, overlap // 2)
    if axis == "x":
        x0, x1 = max(ix0, boundary - half), min(ix1, boundary + half)
        y0, y1 = iy0, iy1
    elif axis == "y":
        x0, x1 = ix0, ix1
        y0, y1 = max(iy0, boundary - half), min(iy1, boundary + half)
    else:
        raise ValueError("unknown tile seam axis")
    if x0 >= x1 or y0 >= y1:
        raise ValueError("native tile seam has no validation band")

    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        left_box = (
            (x0 - ax0) * 2, (y0 - ay0) * 2,
            (x1 - ax0) * 2, (y1 - ay0) * 2,
        )
        right_box = (
            (x0 - bx0) * 2, (y0 - by0) * 2,
            (x1 - bx0) * 2, (y1 - by0) * 2,
        )
        left_pixels = np.asarray(left_image.crop(left_box).convert("RGB"), dtype=np.int16)
        right_pixels = np.asarray(right_image.crop(right_box).convert("RGB"), dtype=np.int16)
    if left_pixels.shape != right_pixels.shape or left_pixels.size == 0:
        raise ValueError("native tile seam comparison geometry differs")
    delta = np.abs(left_pixels - right_pixels)
    return int(delta.max()), float(delta.mean())


def _write_core(
    raw,
    candidate_path: Path,
    v2_region,
    *,
    source_mode: str,
    target_width: int,
    core_rect: tuple[int, int, int, int],
    tile_rect: tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = core_rect
    tx0, ty0, _, _ = tile_rect
    global_x, global_y = x0 * 2, y0 * 2
    width, height = (x1 - x0) * 2, (y1 - y0) * 2
    local_box = (
        (x0 - tx0) * 2, (y0 - ty0) * 2,
        (x1 - tx0) * 2, (y1 - ty0) * 2,
    )
    with Image.open(candidate_path) as image:
        rgb = np.asarray(image.crop(local_box).convert("RGB"), dtype=np.uint8)
    if rgb.shape[:2] != (height, width):
        raise ValueError("native tile core has an unexpected size")

    if source_mode == "RGBA":
        alpha_bytes = v2_region.fetch(global_x, global_y, width, height)
        alpha_rgba = np.frombuffer(alpha_bytes, dtype=np.uint8).reshape(height, width, 4)
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        pixels[..., :3] = rgb
        pixels[..., 3] = alpha_rgba[..., 3]
    else:
        pixels = rgb

    channels = 4 if source_mode == "RGBA" else 3
    row_bytes = target_width * channels
    for row in range(height):
        raw.seek((global_y + row) * row_bytes + global_x * channels)
        raw.write(pixels[row].tobytes())


def run_tiled_candidates(
    source: Path,
    v2_reference: Path,
    output_dir: Path,
    target_size: tuple[int, int],
    processors: Mapping[str, Callable[[Path, Path], None]],
    *,
    tile_size: int = DEFAULT_TILE_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
    execution_records: dict | None = None,
) -> dict[str, object]:
    """Run four sequential native 2x engines with bounded memory and disk stitching.

    The output core of each tile is written once to a raw disk raster. Adjacent
    overlapping predictions are compared before stitching; excessive seam
    disagreement rejects that engine candidate. RGBA output alpha is copied
    from the accepted V2 reference, never reconstructed from model pixels.
    """
    source, v2_reference, output_dir = map(Path, (source, v2_reference, output_dir))
    if set(processors) != set(ENGINES):
        raise ValueError("exactly four native processors are required")
    if not isinstance(target_size, (tuple, list)) or len(target_size) != 2:
        raise ValueError("target size must contain width and height")
    if any(not isinstance(value, int) or value < 1 for value in target_size):
        raise ValueError("target dimensions must be positive integers")
    if tile_size < 64 or overlap < 8 or overlap * 2 >= tile_size:
        raise ValueError("tile size/overlap are outside the safe configuration")
    if source.suffix.lower() != ".png" or v2_reference.suffix.lower() != ".png":
        raise RuntimeError("disk-backed native tile inference currently requires PNG source and V2 reference")
    if not source.is_file() or not v2_reference.is_file():
        raise FileNotFoundError("native tile source or accepted V2 reference is missing")
    if source.resolve() == v2_reference.resolve():
        raise ValueError("native tile source and V2 reference must be different files")

    with _open_fusion_image(source) as source_image, _open_fusion_image(v2_reference) as v2_image:
        source_size = source_image.size
        if min(source_size) < 64:
            raise ValueError("native tile inference requires source dimensions of at least 64 pixels")
        if (target_size[0], target_size[1]) != (source_size[0] * 2, source_size[1] * 2):
            raise ValueError("disk-backed native tile inference supports one exact 2x native pass")
        if source_image.mode not in ("RGB", "RGBA") or v2_image.mode != source_image.mode:
            raise ValueError("native tile source and V2 reference must have matching RGB/RGBA modes")
        if v2_image.size != tuple(target_size):
            raise ValueError("accepted V2 reference dimensions differ from target")
        source_metadata = {
            key: source_image.info[key]
            for key in ("icc_profile", "dpi") if key in source_image.info
        }
        v2_metadata = {
            key: v2_image.info[key]
            for key in ("icc_profile", "dpi") if key in v2_image.info
        }
        if source_metadata.get("icc_profile") != v2_metadata.get("icc_profile"):
            raise ValueError("source and accepted V2 ICC profiles differ")
        mode = source_image.mode

    width, height = map(int, target_size)
    pixels = width * height
    channels = 4 if mode == "RGBA" else 3
    row_bytes = width * channels
    if pixels > MAX_STREAMED_PIXELS:
        raise RuntimeError("native tile target exceeds the safe disk-streaming pixel limit")
    if row_bytes > MAX_STREAMED_ROW_BYTES:
        raise RuntimeError("native tile target row exceeds the safe streaming buffer limit")
    raw_bytes = row_bytes * height
    disk_root = output_dir.parent if output_dir.parent.exists() else Path.cwd()
    # Reserve worst-case uncompressed space for all four candidate PNGs plus
    # the disk-backed fusion raster and its atomic streamed-PNG temporary.
    # PNG compression is not a safe capacity estimate for customer artwork.
    required_disk_bytes = _required_disk_bytes(
        raw_bytes, remaining_candidates=len(ENGINES)
    )
    if shutil.disk_usage(disk_root).free < required_disk_bytes:
        raise DiskReserveError(
            "insufficient free disk space for four native candidates and fusion workspace"
        )

    try:
        import pyvips
    except ImportError as exc:
        raise RuntimeError("pyvips is required for disk-backed native tile inference") from exc

    source_vips, source_region = _open_vips_region(source, source_size, mode)
    v2_vips, v2_region = _open_vips_region(v2_reference, tuple(target_size), mode)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_width, source_height = source_size
    columns = (source_width + tile_size - 1) // tile_size
    rows = (source_height + tile_size - 1) // tile_size
    total_tiles = columns * rows
    candidates: list[Candidate] = []
    failures: dict[str, str] = {}
    tile_reports: dict[str, dict] = {}
    all_candidate_paths = [output_dir / (name + ".png") for name in ENGINES]

    def discard_all() -> None:
        for path in all_candidate_paths:
            path.unlink(missing_ok=True)

    try:
        for engine_index, name in enumerate(ENGINES):
            destination = output_dir / (name + ".png")
            destination.unlink(missing_ok=True)
            seam_count = 0
            seam_max = 0
            seam_mean_sum = 0.0
            tile_count = 0
            tile_process_count = 0
            tile_process_elapsed_ms_total = 0.0
            try:
                # Completed candidates remain on disk. Count their actual
                # bytes and reserve raw-raster space for every engine still to run.
                completed_candidate_bytes = sum(
                    candidate.path.stat().st_size for candidate in candidates
                )
                required_disk_bytes = _required_disk_bytes(
                    raw_bytes,
                    remaining_candidates=len(ENGINES) - engine_index,
                    completed_candidate_bytes=completed_candidate_bytes,
                )
                if shutil.disk_usage(disk_root).free < required_disk_bytes:
                    raise DiskReserveError(
                        "free disk space fell below the remaining candidate and fusion reserve"
                    )
                with TemporaryDirectory(prefix=".v211_" + name + "_tiles_", dir=output_dir) as temp_name:
                    temp_dir = Path(temp_name)
                    with TemporaryFile(mode="w+b", dir=output_dir) as raw:
                        raw.truncate(raw_bytes)
                        previous_row: dict[int, tuple[Path, tuple[int, int, int, int]]] = {}
                        for row_index, y0 in enumerate(range(0, source_height, tile_size)):
                            current_row: dict[int, tuple[Path, tuple[int, int, int, int]]] = {}
                            y1 = min(source_height, y0 + tile_size)
                            for column_index, x0 in enumerate(range(0, source_width, tile_size)):
                                if cancel_check and cancel_check():
                                    discard_all()
                                    raise InterruptedError("Processing stopped by user")
                                x1 = min(source_width, x0 + tile_size)
                                tx0, tx1 = _expand_interval(x0, x1, source_width, overlap)
                                ty0, ty1 = _expand_interval(y0, y1, source_height, overlap)
                                tile_rect = (tx0, ty0, tx1, ty1)
                                tile_source = temp_dir / ("tile-r" + str(row_index) + "-c" + str(column_index) + ".png")
                                tile_output = temp_dir / ("candidate-r" + str(row_index) + "-c" + str(column_index) + ".png")
                                tile_image = _read_region(
                                    source_region, mode, tile_rect
                                )
                                try:
                                    tile_image.save(tile_source, format="PNG", **source_metadata)
                                finally:
                                    tile_image.close()
                                if cancel_check and cancel_check():
                                    discard_all()
                                    raise InterruptedError("Processing stopped by user")
                                try:
                                    processors[name](tile_source, tile_output)
                                finally:
                                    if execution_records is not None:
                                        process_record = execution_records.get(name)
                                        if isinstance(process_record, dict):
                                            elapsed = process_record.get("process_elapsed_ms")
                                            if isinstance(elapsed, (int, float)) and elapsed >= 0:
                                                tile_process_elapsed_ms_total += float(elapsed)
                                            if process_record.get("process_started") is True:
                                                tile_process_count += 1
                                _validate_tile_output(
                                    tile_output,
                                    ((tx1 - tx0) * 2, (ty1 - ty0) * 2),
                                    mode,
                                    source_metadata,
                                )
                                tile_count += 1

                                if column_index > 0:
                                    left_path, left_rect = current_row[column_index - 1]
                                    maximum, mean = _compare_overlap(
                                        left_path, left_rect, tile_output, tile_rect,
                                        axis="x", boundary=x0, overlap=overlap,
                                    )
                                    seam_count += 1
                                    seam_max = max(seam_max, maximum)
                                    seam_mean_sum += mean
                                    if maximum > SEAM_MAX_CHANNEL_DELTA or mean > SEAM_MEAN_CHANNEL_DELTA:
                                        raise ValueError("horizontal native tile seam disagreement exceeds the fail-closed threshold")
                                if row_index > 0:
                                    above_path, above_rect = previous_row[column_index]
                                    maximum, mean = _compare_overlap(
                                        above_path, above_rect, tile_output, tile_rect,
                                        axis="y", boundary=y0, overlap=overlap,
                                    )
                                    seam_count += 1
                                    seam_max = max(seam_max, maximum)
                                    seam_mean_sum += mean
                                    if maximum > SEAM_MAX_CHANNEL_DELTA or mean > SEAM_MEAN_CHANNEL_DELTA:
                                        raise ValueError("vertical native tile seam disagreement exceeds the fail-closed threshold")

                                _write_core(
                                    raw, tile_output, v2_region,
                                    source_mode=mode, target_width=width,
                                    core_rect=(x0, y0, x1, y1), tile_rect=tile_rect,
                                )
                                current_row[column_index] = (tile_output, tile_rect)
                                tile_source.unlink(missing_ok=True)
                                if progress_callback:
                                    progress_callback(
                                        96 + engine_index,
                                        "NiyomSilp Design · Four AI · " + name
                                        + " · tile " + str(tile_count) + "/" + str(total_tiles),
                                    )
                            for old_path, _ in previous_row.values():
                                old_path.unlink(missing_ok=True)
                            previous_row = current_row
                        for old_path, _ in previous_row.values():
                            old_path.unlink(missing_ok=True)

                        if cancel_check and cancel_check():
                            discard_all()
                            raise InterruptedError("Processing stopped by user")
                        _write_streamed_png(
                            raw, destination, tuple(target_size), mode,
                            v2_metadata, cancel_check,
                        )
                tile_reports[name] = {
                    "status": "stitched",
                    "tile_count": tile_count,
                    "tile_process_count": tile_process_count,
                    "tile_process_elapsed_ms_total": round(tile_process_elapsed_ms_total, 3),
                    "seam_count": seam_count,
                    "seam_max_channel_delta": seam_max,
                    "seam_mean_channel_delta": (
                        seam_mean_sum / seam_count if seam_count else 0.0
                    ),
                    "seam_max_limit": SEAM_MAX_CHANNEL_DELTA,
                    "seam_mean_limit": SEAM_MEAN_CHANNEL_DELTA,
                    "seam_validation": "passed",
                    "output_pixels": pixels,
                }
                candidates.append(Candidate(name, destination, width, height))
            except InterruptedError:
                discard_all()
                raise
            except Exception as exc:
                destination.unlink(missing_ok=True)
                failures[name] = type(exc).__name__ + ": " + str(exc)
                tile_reports[name] = {
                    "status": "rejected",
                    "tile_count": tile_count,
                    "tile_process_count": tile_process_count,
                    "tile_process_elapsed_ms_total": round(tile_process_elapsed_ms_total, 3),
                    "seam_count": seam_count,
                    "seam_max_channel_delta": seam_max,
                    "seam_validation": "failed",
                    "error_type": type(exc).__name__,
                }
                if isinstance(exc, DiskReserveError):
                    # Once the full four-engine workspace cannot be reserved,
                    # stop the run rather than opportunistically launching later
                    # engines with an incomplete candidate set.
                    for pending_name in ENGINES[engine_index + 1:]:
                        failures[pending_name] = (
                            "DiskReserveError: not_started_after_disk_reserve_failure"
                        )
                        tile_reports[pending_name] = {
                            "status": "not_started",
                            "tile_count": 0,
                            "tile_process_count": 0,
                            "tile_process_elapsed_ms_total": 0.0,
                            "seam_count": 0,
                            "seam_max_channel_delta": 0,
                            "seam_validation": "not_run",
                            "error_type": "DiskReserveError",
                        }
                    break
            finally:
                if execution_records is not None and isinstance(execution_records.get(name), dict):
                    execution_records[name]["tile_count"] = tile_count
                    execution_records[name]["tile_process_count"] = tile_process_count
                    execution_records[name]["tile_process_elapsed_ms_total"] = round(tile_process_elapsed_ms_total, 3)
                    execution_records[name]["tile_seam_count"] = seam_count
                    execution_records[name]["tile_seam_max_channel_delta"] = seam_max
                    execution_records[name]["tile_process_scope"] = "all_tiles_aggregated"
        return {
            "research_only": True,
            "fusion_implemented": False,
            "quality_certified": False,
            "candidates": candidates,
            "failures": failures,
            "ready_for_fusion_research": len(candidates) == len(ENGINES),
            "native_tiled_inference": {
                "implemented": True,
                "tile_size": tile_size,
                "overlap": overlap,
                "native_scale": 2,
                "execution_order": list(ENGINES),
                "engine_results": tile_reports,
                "all_four_engines_completed": len(candidates) == len(ENGINES),
                "gpu_adapter_verified": False,
            },
        }
    except InterruptedError:
        discard_all()
        raise
    finally:
        source_region = None
        v2_region = None
        source_vips = None
        v2_vips = None
