"""Create a private V2 vs V2.1.1 A/B pack.

The bridge sidecar is unsigned: this tool checks its schema and file-hash
bindings, but does not cryptographically authenticate the sidecar's claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import warnings

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.v211_four_engine_fusion import (
    MAX_PNG_ICC_BYTES, MAX_RGBA_VALIDATION_PIXELS, MAX_STREAMED_PIXELS,
    MAX_STREAMED_ROW_BYTES, _FusionRaster, _open_fusion_image,
)

ENGINES = ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
TILE_SIZE = 512
MAX_CROPS = 32
MAX_CROP_EDGE = 2048
REVIEW_REGION_LABELS = (
    "face", "animal", "object", "frame", "thai_text", "english_text",
    "chinese_text", "flat_color", "gradient", "rgba_edge",
)
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


TIFF_SUFFIXES = {".tif", ".tiff", ".btf"}
JPEG_SUFFIXES = {".jpg", ".jpeg"}


def _tiff_tag_value(page, code: int):
    tag = page.tags.get(code)
    return None if tag is None else tag.value


def _tiff_rational(value) -> float:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        numerator, denominator = value
        denominator = float(denominator)
        if denominator == 0:
            raise ABReportError("TIFF resolution rational has a zero denominator")
        return float(numerator) / denominator
    return float(value)


def _is_tiff_alpha_extra(value) -> bool:
    name = str(getattr(value, "name", "")).upper()
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        numeric = -1
    return name in ("ASSOCALPHA", "UNASSALPHA") or numeric in (1, 2)


def _tiff_metadata(path: Path) -> dict:
    try:
        import tifffile
    except ImportError as exc:
        raise ABReportError("tifffile is required for TIFF/BigTIFF A/B references") from exc

    with tifffile.TiffFile(str(path)) as tif:
        if len(tif.pages) != 1:
            raise ABReportError("A/B TIFF reference must contain exactly one page")
        page = tif.pages[0]
        shape = tuple(int(value) for value in page.shape)
        if page.dtype != np.dtype("uint8"):
            raise ABReportError("A/B TIFF reference must be 8-bit")
        if int(page.photometric) != 2:
            raise ABReportError("A/B TIFF reference must use RGB photometric data")
        samples = int(page.samplesperpixel or 1)
        if len(shape) != 3 or shape[2] != samples:
            raise ABReportError("planar or non-interleaved TIFF is not supported for A/B")
        if samples == 3:
            mode = "RGB"
        elif samples == 4 and any(_is_tiff_alpha_extra(item) for item in (page.extrasamples or ())):
            mode = "RGBA"
        else:
            raise ABReportError("A/B TIFF reference must be RGB or RGBA with an explicit alpha tag")

        height, width = shape[:2]
        if (width < 1 or height < 1 or width * height > MAX_STREAMED_PIXELS
                or width * samples > MAX_STREAMED_ROW_BYTES):
            raise ABReportError("A/B TIFF reference exceeds the safe streaming limits")

        orientation = _tiff_tag_value(page, 274)
        if orientation not in (None, 1):
            raise ABReportError("rotated TIFF orientation must be normalized before A/B")

        icc_value = _tiff_tag_value(page, 34675)
        if icc_value is None:
            icc_profile = None
        elif isinstance(icc_value, (bytes, bytearray)):
            icc_profile = bytes(icc_value)
            if not icc_profile or len(icc_profile) > MAX_PNG_ICC_BYTES:
                raise ABReportError("TIFF ICC profile is empty or exceeds the safe metadata limit")
        else:
            raise ABReportError("TIFF ICC profile tag is not a byte stream")

        x_tag = _tiff_tag_value(page, 282)
        y_tag = _tiff_tag_value(page, 283)
        unit_tag = _tiff_tag_value(page, 296)
        if (x_tag is None) != (y_tag is None):
            raise ABReportError("TIFF X/Y resolution tags must either both exist or both be absent")
        dpi = None
        if x_tag is not None:
            x_resolution = _tiff_rational(x_tag)
            y_resolution = _tiff_rational(y_tag)
            unit = 1 if unit_tag is None else int(unit_tag)
            if unit == 2:
                dpi = (x_resolution, y_resolution)
            elif unit == 3:
                dpi = (x_resolution * 2.54, y_resolution * 2.54)
            elif unit != 1:
                raise ABReportError("TIFF resolution unit is unsupported")
            if dpi is not None and (
                not all(math.isfinite(value) and value > 0 for value in dpi)
            ):
                raise ABReportError("TIFF print resolution is invalid")

        return {
            "size": (width, height),
            "mode": mode,
            "icc_profile": icc_profile,
            "dpi": dpi,
            "format": "TIFF",
            "is_bigtiff": bool(tif.is_bigtiff),
        }


def _jpeg_metadata(path: Path) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with _open_fusion_image(path) as image:
                if image.format != "JPEG" or image.mode != "RGB":
                    raise ABReportError("A/B JPEG reference must be 8-bit RGB; grayscale and CMYK JPEG are not supported")
                try:
                    orientation = image.getexif().get(274)
                except Exception as exc:
                    raise ABReportError("JPEG EXIF orientation could not be validated") from exc
                if orientation not in (None, 1):
                    raise ABReportError("JPEG EXIF orientation must be normalized to 1 before A/B")
                width, height = (int(value) for value in image.size)
                if (width < 1 or height < 1 or width * height > MAX_STREAMED_PIXELS
                        or width * 3 > MAX_STREAMED_ROW_BYTES):
                    raise ABReportError("A/B JPEG reference exceeds the safe streaming limits")
                icc_profile = image.info.get("icc_profile")
                if icc_profile is not None:
                    if (not isinstance(icc_profile, (bytes, bytearray)) or not icc_profile
                            or len(icc_profile) > MAX_PNG_ICC_BYTES):
                        raise ABReportError("JPEG ICC profile is invalid or exceeds the safe metadata limit")
                    icc_profile = bytes(icc_profile)
                dpi = image.info.get("dpi")
                if dpi is not None:
                    if (not _dpi_equal(dpi, dpi)
                            or any(float(value) <= 0 for value in dpi)):
                        raise ABReportError("JPEG print resolution metadata is invalid")
                    dpi = tuple(float(value) for value in dpi)
                return {
                    "size": (width, height),
                    "mode": "RGB",
                    "icc_profile": icc_profile,
                    "dpi": dpi,
                    "format": "JPEG",
                    "is_bigtiff": False,
                    "exif_orientation": 1 if orientation is None else orientation,
                }
    except Image.DecompressionBombError as exc:
        raise ABReportError("JPEG reference exceeds the safe metadata inspection limit") from exc


def _metadata(path: Path) -> dict:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in TIFF_SUFFIXES:
        return _tiff_metadata(path)
    if suffix in JPEG_SUFFIXES:
        return _jpeg_metadata(path)
    with _open_fusion_image(path) as image:
        if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
            raise ABReportError("A/B candidate must be 8-bit RGB/RGBA PNG; V2 reference may also be JPEG or TIFF/BigTIFF")
        width, height = image.size
        if width < 1 or height < 1 or width * height > MAX_STREAMED_PIXELS:
            raise ABReportError("A/B raster exceeds the safe streaming pixel limit")
        return {
            "size": (int(width), int(height)),
            "mode": image.mode,
            "icc_profile": image.info.get("icc_profile"),
            "dpi": image.info.get("dpi"),
            "format": "PNG",
            "is_bigtiff": False,
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
    engine_count = evidence.get("completed_engine_count")
    if (
        type(engine_count) is not int or engine_count != 4
        or not isinstance(names, list) or len(names) != 4
        or any(not isinstance(name, str) for name in names)
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
    effect_verified = evidence.get("engine_pixel_effect_verified")
    if (
        not isinstance(effect_verified, dict)
        or set(effect_verified) != set(ENGINES)
        or any(effect_verified.get(name) is not True for name in ENGINES)
    ):
        reasons.append("engine_pixel_effect_not_verified_for_all_engines")
    effect_pixels = evidence.get("engine_pixel_effect_pixels")
    if (
        not isinstance(effect_pixels, dict)
        or set(effect_pixels) != set(ENGINES)
        or any(
            type(effect_pixels.get(name)) is not int or effect_pixels.get(name) <= 0
            for name in ENGINES
        )
    ):
        reasons.append("engine_pixel_effect_pixels_incomplete")
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


def parse_crop_label(value: str) -> str:
    """Parse a user-selected semantic label for a human-review crop."""
    label = str(value).strip().lower()
    if label not in REVIEW_REGION_LABELS:
        raise argparse.ArgumentTypeError(
            "crop label must be one of: " + ", ".join(REVIEW_REGION_LABELS)
        )
    return label


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


def _open_vips_tiff(path: Path, mode: str, size: tuple[int, int]):
    try:
        import pyvips
    except ImportError as exc:
        raise ABReportError("pyvips is required for TIFF/BigTIFF region access") from exc
    image = pyvips.Image.new_from_file(
        str(path), access="random", fail_on="error", unlimited=True, page=0,
    )
    expected_bands = 4 if mode == "RGBA" else 3
    if ((image.width, image.height) != size or image.format != "uchar"
            or image.bands != expected_bands):
        raise ABReportError("libvips TIFF pixels differ from the validated 8-bit RGB/RGBA metadata")
    return image


def _open_vips_jpeg(path: Path, mode: str, size: tuple[int, int]):
    if mode != "RGB":
        raise ABReportError("libvips JPEG A/B region access requires RGB")
    try:
        import pyvips
    except ImportError as exc:
        raise ABReportError("pyvips is required for large JPEG A/B region access") from exc
    image = pyvips.Image.new_from_file(
        str(path), access="random", fail_on="error", unlimited=True,
        autorotate=False,
    )
    if ((image.width, image.height) != size or image.format != "uchar"
            or image.bands != 3):
        raise ABReportError("libvips JPEG pixels differ from the validated 8-bit RGB metadata")
    return image


class _ABRaster:
    """Bounded crop reader for PNG, JPEG and single-page TIFF/BigTIFF references."""

    def __init__(self, path: Path, mode: str, size: tuple[int, int], *, use_vips: bool):
        self.path = Path(path)
        self.mode = mode
        self._reader = None
        self._image = None
        self._region = None
        suffix = self.path.suffix.lower()
        if suffix in TIFF_SUFFIXES:
            import pyvips
            self._image = _open_vips_tiff(self.path, mode, size)
            self._region = pyvips.Region.new(self._image)
        elif suffix in JPEG_SUFFIXES and use_vips:
            import pyvips
            self._image = _open_vips_jpeg(self.path, mode, size)
            self._region = pyvips.Region.new(self._image)
        else:
            self._reader = _FusionRaster(self.path, use_vips=use_vips)

    def crop(self, box: tuple[int, int, int, int]) -> Image.Image:
        if self._region is None:
            return self._reader.crop(box)
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        pixels = self._region.fetch(left, top, width, height)
        expected = width * height * (4 if self.mode == "RGBA" else 3)
        if len(pixels) != expected:
            raise ABReportError("libvips returned an incomplete streamed A/B tile")
        return Image.frombytes(self.mode, (width, height), pixels)

    def close(self) -> None:
        self._region = None
        self._image = None
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def _thumbnail(path: Path, mode: str, size: tuple[int, int], max_edge: int) -> Image.Image:
    width, height = size
    suffix = Path(path).suffix.lower()
    if suffix not in TIFF_SUFFIXES and width * height <= MAX_RGBA_VALIDATION_PIXELS:
        with Image.open(path) as image:
            preview = image.copy()
        preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return preview
    if suffix in TIFF_SUFFIXES:
        image = _open_vips_tiff(Path(path), mode, size)
    elif suffix in JPEG_SUFFIXES:
        image = _open_vips_jpeg(Path(path), mode, size)
    else:
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
    return Image.frombytes(mode, (int(image.width), int(image.height)), image.write_to_memory())


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


def run(source, v2_reference, candidate, evidence, output_dir, *, crops=(), crop_labels=(), max_preview_edge=1600):
    source, v2_reference, candidate, evidence = map(
        Path, (source, v2_reference, candidate, evidence)
    )
    requested_crops = tuple(crops)
    requested_labels = tuple(crop_labels)
    output_dir = _ensure_private_output_dir(Path(output_dir))
    report = {
        "schema_version": 1, "status": "blocked", "block_reasons": [],
        "source_v2_pair_bound_by_bridge": False,
        "evidence_metadata_consistent": False,
        "evidence_verified": False,
        "evidence_authenticity_verified": False,
        "quality_certified": False, "visual_quality_certified": False,
        "print_quality_certified": False, "human_review_required": True,
        "delta_metrics_are_quality_scores": False, "artifacts": [],
        "review_regions": [], "review_region_labels_are_user_supplied": bool(requested_labels),
    }
    if not all(path.is_file() for path in (source, v2_reference, candidate, evidence)):
        report["block_reasons"].append("required_input_missing")
        _write_report(output_dir, report)
        return report
    if v2_reference.resolve() == candidate.resolve():
        report["block_reasons"].append("v2_and_candidate_must_be_different_files")
        _write_report(output_dir, report)
        return report
    if (v2_reference.suffix.lower() not in TIFF_SUFFIXES | JPEG_SUFFIXES | {".png"}
            or candidate.suffix.lower() != ".png"):
        report["block_reasons"].append(
            "v2_reference_must_be_png_jpeg_or_tiff_and_candidate_must_be_png"
        )
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
    report["evidence_metadata_consistent"] = True

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
    crop_boxes = list(requested_crops) if requested_crops else _default_crops(width, height)
    if requested_labels and not requested_crops:
        report["block_reasons"].append("crop_labels_require_explicit_crops")
        _write_report(output_dir, report)
        return report
    if requested_labels and len(requested_labels) != len(crop_boxes):
        report["block_reasons"].append("crop_label_count_mismatch")
        _write_report(output_dir, report)
        return report
    if any(not isinstance(label, str) or label not in REVIEW_REGION_LABELS for label in requested_labels):
        report["block_reasons"].append("crop_label_invalid")
        _write_report(output_dir, report)
        return report
    if len(crop_boxes) > MAX_CROPS:
        report["block_reasons"].append("too_many_review_crops")
        _write_report(output_dir, report)
        return report
    review_labels = list(requested_labels) if requested_labels else [
        f"region_{index:02d}" for index in range(1, len(crop_boxes) + 1)
    ]
    large = width * height > MAX_RGBA_VALIDATION_PIXELS
    try:
        with (
            _ABRaster(v2_reference, v2_info["mode"], v2_info["size"], use_vips=large) as v2_raster,
            _ABRaster(candidate, candidate_info["mode"], candidate_info["size"], use_vips=large) as candidate_raster,
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

            review_regions = []
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
                label = review_labels[index - 1]
                filename = f"ab_crop_{index:02d}_{label}.png"
                crop_sheet.save(output_dir / filename, format="PNG")
                left_crop.close()
                right_crop.close()
                crop_sheet.close()
                report["artifacts"].append(filename)
                review_regions.append({
                    "label": label,
                    "box_xywh": [x, y, crop_width, crop_height],
                    "artifact": filename,
                })
            report["review_regions"] = review_regions
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
        "evidence_metadata_consistent": True,
        "evidence_verified": False,
        "evidence_authenticity_verified": False,
        "evidence_verification_scope": (
            "unsigned sidecar schema and SHA256 bindings checked; bridge claims are "
            "not cryptographically authenticated"
        ),
        "source_sha256": source_sha,
        "v2_reference_sha256": v2_sha,
        "qa_image_sha256": candidate_sha,
        "target_size": [width, height],
        "mode": mode,
        "icc_profile_match": True,
        "dpi_match": True,
        "streamed_large_image": large,
        "streamed_raster_access": large or v2_info["format"] == "TIFF",
        "v2_reference_format": v2_info["format"],
        "v2_reference_is_bigtiff": v2_info["is_bigtiff"],
        "v2_reference_exif_orientation": v2_info.get("exif_orientation"),
        "candidate_format": candidate_info["format"],
        "tiff_region_access": v2_info["format"] == "TIFF",
        "jpeg_region_access": v2_info["format"] == "JPEG" and large,
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
    parser.add_argument(
        "--crop-label", type=parse_crop_label, action="append", default=[],
        help="User-selected label for each --crop, in the same order; may be repeated",
    )
    parser.add_argument("--max-preview-edge", type=int, default=1600)
    args = parser.parse_args()
    try:
        report = run(
            args.source, args.v2_reference, args.candidate, args.evidence,
            args.output_dir, crops=tuple(args.crop), crop_labels=tuple(args.crop_label),
            max_preview_edge=args.max_preview_edge,
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
