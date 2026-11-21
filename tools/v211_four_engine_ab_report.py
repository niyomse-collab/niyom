"""Create a private, evidence-bound V2 vs V2.1.1 four-engine visual A/B pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.v211_four_engine_fusion import (
    MAX_RGBA_VALIDATION_PIXELS, MAX_STREAMED_PIXELS,
    _FusionRaster, _open_fusion_image,
)

ENGINES = ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
TILE_SIZE = 512
MAX_CROPS = 32
MAX_CROP_EDGE = 2048
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ABReportError(ValueError):
    """Invalid local A/B evidence or image contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _dpi_equal(left, right) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if not isinstance(left, (tuple, list)) or not isinstance(right, (tuple, list)):
        return False
    if len(left) != 2 or len(right) != 2:
        return False
    try:
        return all(
            math.isfinite(float(a)) and math.isfinite(float(b))
            and abs(float(a) - float(b)) <= 0.1
            for a, b in zip(left, right)
        )
    except (TypeError, ValueError, OverflowError):
        return False


def _metadata(path: Path) -> dict:
    with _open_fusion_image(path) as image:
        if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
            raise ABReportError("A/B rasters must be 8-bit RGB/RGBA PNG")
        width, height = image.size
        if width < 1 or height < 1 or width * height > MAX_STREAMED_PIXELS:
            raise ABReportError("A/B raster exceeds the safe streaming pixel limit")
        return {
            "size": (int(width), int(height)),
            "mode": image.mode,
            "icc_profile": image.info.get("icc_profile"),
            "dpi": image.info.get("dpi"),
        }


def _verify_evidence(
    evidence_path: Path, *, source_sha256: str, v2_sha256: str,
    candidate_sha256: str,
) -> list[str]:
    try:
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["evidence_json_unreadable"]
    if not isinstance(evidence, dict):
        return ["evidence_json_invalid"]
    reasons = []
    if evidence.get("schema_version") != 1:
        reasons.append("evidence_schema_mismatch")
    if evidence.get("evidence_type") != "niyomsil_v211_four_engine_qa":
        reasons.append("evidence_type_mismatch")
    if evidence.get("source_v2_pair_bound_by_bridge") is not True:
        reasons.append("source_v2_pair_not_bound_by_bridge")
    if evidence.get("source_sha256") != source_sha256:
        reasons.append("source_sha256_mismatch")
    if evidence.get("v2_reference_sha256") != v2_sha256:
        reasons.append("v2_reference_sha256_mismatch")
    if evidence.get("qa_image_sha256") != candidate_sha256:
        reasons.append("qa_image_sha256_mismatch")
    names = evidence.get("completed_engine_names")
    if (
        evidence.get("completed_engine_count") != 4
        or not isinstance(names, list) or len(names) != 4
        or set(names) != set(ENGINES)
    ):
        reasons.append("four_native_engines_not_complete")
    per_engine = evidence.get("per_engine_runtime_device_use_verified")
    if (
        evidence.get("runtime_device_use_verified") is not True
        or not isinstance(per_engine, dict) or set(per_engine) != set(ENGINES)
        or not all(per_engine.get(name) is True for name in ENGINES)
    ):
        reasons.append("physical_gpu_adapter_not_verified_for_all_engines")
    for key in (
        "fusion_implemented", "all_four_engine_candidates_consumed",
        "all_four_engine_pixels_contributed", "v2_output_preserved",
    ):
        if evidence.get(key) is not True:
            reasons.append(key + "_not_verified")
    candidate_hashes = evidence.get("engine_candidate_sha256")
    if (
        not isinstance(candidate_hashes, dict) or set(candidate_hashes) != set(ENGINES)
        or not all(_valid_sha(candidate_hashes.get(name)) for name in ENGINES)
    ):
        reasons.append("engine_candidate_hash_manifest_incomplete")
    for key in ("native_seed_sha256", "native_v2_reference_sha256", "fusion_output_sha256"):
        if not _valid_sha(evidence.get(key)):
            reasons.append(key + "_missing")
    privacy = evidence.get("privacy")
    if (
        not isinstance(privacy, dict)
        or any(privacy.get(key) is not False for key in (
            "paths_included", "commands_included", "logs_included", "image_pixels_included"
        ))
    ):
        reasons.append("evidence_privacy_contract_missing")
    if evidence.get("quality_certified") is not False:
        reasons.append("evidence_must_not_claim_quality_certification")
    return reasons


def _ensure_private_output_dir(path: Path) -> Path:
    output = Path(path).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[1]
    if output == repository_root or output.is_relative_to(repository_root):
        raise ABReportError("A/B output must be outside the Git repository")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ABReportError("A/B output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _default_crops(width: int, height: int) -> list[tuple[int, int, int, int]]:
    crop_width, crop_height = min(512, width), min(512, height)
    xs = sorted({0, max(0, (width - crop_width) // 2), max(0, width - crop_width)})
    ys = sorted({0, max(0, (height - crop_height) // 2), max(0, height - crop_height)})
    return [(x, y, crop_width, crop_height) for y in ys for x in xs][:MAX_CROPS]


def parse_crop(value: str) -> tuple[int, int, int, int]:
    try:
        parts = tuple(int(item.strip()) for item in value.split(","))
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("crop must be x,y,width,height")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x,y,width,height")
    x, y, width, height = parts
    if min(x, y) < 0 or min(width, height) < 1 or max(width, height) > MAX_CROP_EDGE:
        raise argparse.ArgumentTypeError("crop must be inside the image and no larger than 2048 pixels")
    return parts


def _display_rgb(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image.convert("RGB")
    background = Image.new("RGB", image.size, (224, 224, 224))
    draw = ImageDraw.Draw(background)
    block = 16
    for y in range(0, image.height, block):
        for x in range(0, image.width, block):
            if ((x // block) + (y // block)) % 2:
                draw.rectangle(
                    (x, y, min(image.width - 1, x + block - 1),
                     min(image.height - 1, y + block - 1)),
                    fill=(184, 184, 184),
                )
    background.paste(image, (0, 0), image.getchannel("A"))
    return background


def _comparison_sheet(left: Image.Image, right: Image.Image) -> Image.Image:
    left_rgb, right_rgb = _display_rgb(left), _display_rgb(right)
    header, gutter = 34, 16
    sheet = Image.new(
        "RGB", (left_rgb.width + right_rgb.width + gutter,
                max(left_rgb.height, right_rgb.height) + header),
        (32, 32, 32),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((4, 8), "ACCEPTED V2", fill="white", font=font)
    draw.text((left_rgb.width + gutter + 4, 8), "V2.1.1 FOUR-ENGINE QA", fill="white", font=font)
    sheet.paste(left_rgb, (0, header))
    sheet.paste(right_rgb, (left_rgb.width + gutter, header))
    left_rgb.close()
    right_rgb.close()
    return sheet


def _thumbnail(path: Path, mode: str, size: tuple[int, int], max_edge: int) -> Image.Image:
    width, height = size
    if width * height <= MAX_RGBA_VALIDATION_PIXELS:
        with Image.open(path) as image:
            preview = image.copy()
        preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return preview
    try:
        import pyvips
    except ImportError as exc:
        raise ABReportError("pyvips is required for A/B previews above 18 MP") from exc
    image = pyvips.Image.new_from_file(
        str(path), access="random", fail_on="error", unlimited=True,
    )
    expected_bands = 4 if mode == "RGBA" else 3
    if image.format != "uchar" or image.bands != expected_bands:
        raise ABReportError("large A/B preview must decode as 8-bit RGB/RGBA")
    scale = min(1.0, float(max_edge) / max(width, height))
    if scale < 1.0:
        image = image.resize(scale, kernel="lanczos3")
    return Image.frombytes(mode, (image.width, image.height), image.write_to_memory())


def _compute_metrics(v2_raster, candidate_raster, size, mode) -> dict:
    width, height = size
    visible_pixels = changed_pixels = sum_abs = sum_squared = 0
    max_delta = alpha_mismatch = 0
    for y in range(0, height, TILE_SIZE):
        for x in range(0, width, TILE_SIZE):
            box = (x, y, min(width, x + TILE_SIZE), min(height, y + TILE_SIZE))
            left = np.asarray(v2_raster.crop(box), dtype=np.uint8)
            right = np.asarray(candidate_raster.crop(box), dtype=np.uint8)
            if mode == "RGBA":
                alpha_mismatch += int(np.count_nonzero(left[..., 3] != right[..., 3]))
                visible = (left[..., 3] > 0) & (right[..., 3] > 0)
            else:
                visible = np.ones(left.shape[:2], dtype=bool)
            delta = np.abs(left[..., :3].astype(np.int16) - right[..., :3].astype(np.int16))
            if np.any(visible):
                selected = delta[visible]
                visible_pixels += int(np.count_nonzero(visible))
                changed_pixels += int(np.count_nonzero(np.any(selected != 0, axis=1)))
                sum_abs += int(selected.sum(dtype=np.uint64))
                sum_squared += int(np.square(selected.astype(np.int64)).sum())
                max_delta = max(max_delta, int(selected.max()))
    channel_count = visible_pixels * 3
    return {
        "visible_pixels": visible_pixels,
        "changed_visible_pixels": changed_pixels,
        "changed_visible_pixel_fraction": changed_pixels / visible_pixels if visible_pixels else None,
        "mean_abs_rgb_delta": sum_abs / channel_count if channel_count else None,
        "rmse_rgb_delta": math.sqrt(sum_squared / channel_count) if channel_count else None,
        "max_channel_delta": max_delta,
        "alpha_mismatch_pixels": alpha_mismatch,
        "alpha_exact_match": alpha_mismatch == 0 if mode == "RGBA" else None,
        "delta_metrics_are_quality_scores": False,
    }


def _write_report(output_dir: Path, report: dict) -> None:
    (output_dir / "ab_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run(source, v2_reference, candidate, evidence, output_dir, *, crops=(), max_preview_edge=1600):
    source, v2_reference, candidate, evidence = map(
        Path, (source, v2_reference, candidate, evidence)
    )
    output_dir = _ensure_private_output_dir(Path(output_dir))
    report = {
        "schema_version": 1, "status": "blocked", "block_reasons": [],
        "source_v2_pair_bound_by_bridge": False, "evidence_verified": False,
        "quality_certified": False, "visual_quality_certified": False,
        "print_quality_certified": False, "human_review_required": True,
        "delta_metrics_are_quality_scores": False, "artifacts": [],
    }
    if not all(path.is_file() for path in (source, v2_reference, candidate, evidence)):
        report["block_reasons"].append("required_input_missing")
        _write_report(output_dir, report)
        return report
    if v2_reference.resolve() == candidate.resolve():
        report["block_reasons"].append("v2_and_candidate_must_be_different_files")
        _write_report(output_dir, report)
        return report
    if v2_reference.suffix.lower() != ".png" or candidate.suffix.lower() != ".png":
        report["block_reasons"].append("v2_and_candidate_must_be_png")
        _write_report(output_dir, report)
        return report
    if not 256 <= max_preview_edge <= 4096:
        report["block_reasons"].append("preview_edge_out_of_range")
        _write_report(output_dir, report)
        return report

    source_sha, v2_sha, candidate_sha = (
        sha256_file(source), sha256_file(v2_reference), sha256_file(candidate)
    )
    evidence_reasons = _verify_evidence(
        evidence, source_sha256=source_sha, v2_sha256=v2_sha,
        candidate_sha256=candidate_sha,
    )
    if evidence_reasons:
        report["block_reasons"].extend(evidence_reasons)
        _write_report(output_dir, report)
        return report

    try:
        v2_info, candidate_info = _metadata(v2_reference), _metadata(candidate)
    except Exception as exc:
        report["block_reasons"].append("image_preflight_" + type(exc).__name__.lower())
        _write_report(output_dir, report)
        return report
    if v2_info["size"] != candidate_info["size"]:
        report["block_reasons"].append("pixel_dimensions_mismatch")
    if v2_info["mode"] != candidate_info["mode"]:
        report["block_reasons"].append("rgb_rgba_mode_mismatch")
    if v2_info["icc_profile"] != candidate_info["icc_profile"]:
        report["block_reasons"].append("icc_profile_mismatch")
    if not _dpi_equal(v2_info["dpi"], candidate_info["dpi"]):
        report["block_reasons"].append("print_dpi_mismatch")
    if report["block_reasons"]:
        _write_report(output_dir, report)
        return report

    width, height = v2_info["size"]
    mode = v2_info["mode"]
    large = width * height > MAX_RGBA_VALIDATION_PIXELS
    try:
        with (
            _FusionRaster(v2_reference, use_vips=large) as v2_raster,
            _FusionRaster(candidate, use_vips=large) as candidate_raster,
        ):
            metrics = _compute_metrics(v2_raster, candidate_raster, (width, height), mode)
            report["metrics"] = metrics
            if metrics["alpha_exact_match"] is False:
                report["block_reasons"].append("alpha_not_pixel_identical_to_accepted_v2")
            elif metrics["visible_pixels"] < 1:
                report["block_reasons"].append("no_visible_pixels_to_compare")
            if report["block_reasons"]:
                _write_report(output_dir, report)
                return report

            left = _thumbnail(v2_reference, mode, (width, height), max_preview_edge)
            right = _thumbnail(candidate, mode, (width, height), max_preview_edge)
            sheet = _comparison_sheet(left, right)
            sheet.save(output_dir / "ab_contact_sheet.png", format="PNG")
            left.close()
            right.close()
            sheet.close()
            report["artifacts"].append("ab_contact_sheet.png")

            crop_boxes = list(crops) if crops else _default_crops(width, height)
            if len(crop_boxes) > MAX_CROPS:
                raise ABReportError("at most 32 review crops are allowed")
            for index, (x, y, crop_width, crop_height) in enumerate(crop_boxes, start=1):
                if (
                    x < 0 or y < 0 or crop_width < 1 or crop_height < 1
                    or crop_width > MAX_CROP_EDGE or crop_height > MAX_CROP_EDGE
                    or x + crop_width > width or y + crop_height > height
                ):
                    raise ABReportError("review crop is outside the image or exceeds 2048 pixels")
                box = (x, y, x + crop_width, y + crop_height)
                left_crop, right_crop = v2_raster.crop(box), candidate_raster.crop(box)
                crop_sheet = _comparison_sheet(left_crop, right_crop)
                filename = f"ab_crop_{index:02d}.png"
                crop_sheet.save(output_dir / filename, format="PNG")
                left_crop.close()
                right_crop.close()
                crop_sheet.close()
                report["artifacts"].append(filename)
    except Exception as exc:
        for name in report["artifacts"]:
            (output_dir / name).unlink(missing_ok=True)
        report["artifacts"] = []
        report["block_reasons"].append("streaming_or_preview_" + type(exc).__name__.lower())
        _write_report(output_dir, report)
        return report

    report["input_files_unchanged"] = (
        sha256_file(source) == source_sha
        and sha256_file(v2_reference) == v2_sha
        and sha256_file(candidate) == candidate_sha
    )
    if not report["input_files_unchanged"]:
        for name in report["artifacts"]:
            (output_dir / name).unlink(missing_ok=True)
        report["artifacts"] = []
        report["block_reasons"].append("an_input_file_changed_during_comparison")
        _write_report(output_dir, report)
        return report

    report.update({
        "status": "ready_for_human_review",
        "source_v2_pair_bound_by_bridge": True,
        "evidence_verified": True,
        "source_sha256": source_sha,
        "v2_reference_sha256": v2_sha,
        "qa_image_sha256": candidate_sha,
        "target_size": [width, height],
        "mode": mode,
        "icc_profile_match": True,
        "dpi_match": True,
        "streamed_large_image": large,
        "same_source_generation_proven": False,
        "provenance_scope": (
            "the bridge binds this source and accepted V2 file to the same four-engine "
            "invocation; it does not independently prove the historical generation "
            "of the accepted V2 raster"
        ),
        "quality_certified": False,
        "visual_quality_certified": False,
        "print_quality_certified": False,
        "human_review_required": True,
    })
    _write_report(output_dir, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a private V2 vs V2.1.1 A/B review pack.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--v2-reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--crop", type=parse_crop, action="append", default=[])
    parser.add_argument("--max-preview-edge", type=int, default=1600)
    args = parser.parse_args()
    try:
        report = run(
            args.source, args.v2_reference, args.candidate, args.evidence,
            args.output_dir, crops=tuple(args.crop), max_preview_edge=args.max_preview_edge,
        )
    except ABReportError as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        raise SystemExit(2)
    print(json.dumps({
        "status": report["status"], "block_reasons": report["block_reasons"],
        "quality_certified": False,
    }, ensure_ascii=False))
    if report["status"] != "ready_for_human_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
