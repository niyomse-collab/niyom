"""Disk-backed seed preparation and QA cropping for large four-engine jobs.

This helper is research-only. It prepares the exact 2x native input from the
already accepted V2 canvas using libvips regions/streaming, and writes a
separate cropped QA PNG without decoding a large customer raster in Pillow.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import warnings
from uuid import uuid4

from PIL import Image, PngImagePlugin


def _open_vips(path: Path, *, autorot: bool = False):
    from .large_image import vips

    path = Path(path)
    options = {"access": "random", "fail_on": "error"}
    if path.suffix.lower() in (".png", ".tif", ".tiff"):
        options["unlimited"] = True
    image = vips().Image.new_from_file(str(path), **options)
    return image.autorot() if autorot else image


def _vips_mode(image) -> str:
    if image.format != "uchar":
        raise ValueError("large four-engine input requires 8-bit RGB/RGBA pixels")
    if image.bands == 3:
        return "RGB"
    if image.bands == 4 and image.hasalpha():
        return "RGBA"
    raise ValueError("large four-engine input must be RGB or RGBA, not grayscale/CMYK")


def _vips_profile(image):
    try:
        return image.get("icc-profile-data")
    except Exception:
        return None


def _fallback_metadata(image) -> dict:
    metadata = {}
    profile = _vips_profile(image)
    if profile:
        metadata["icc_profile"] = profile
    try:
        dpi_x = float(image.xres) * 25.4
        dpi_y = float(image.yres) * 25.4
        # libvips uses 1 pixel/mm as its untagged default. Do not invent a
        # print resolution when the source container did not carry one.
        if abs(float(image.xres) - 1.0) > 1e-6 or abs(float(image.yres) - 1.0) > 1e-6:
            metadata["dpi"] = (dpi_x, dpi_y)
    except (AttributeError, TypeError, ValueError):
        pass
    return metadata


def _header_exif_orientation(image) -> int | None:
    """Read EXIF orientation from container metadata without decoding pixels.

    Pillow's PNG getexif() calls load() when the file has no cached EXIF data.
    That would decode the entire PNG before a large-image job reaches libvips.
    PNG eXIf chunks are already captured in image.info during header parsing,
    so parse those bytes directly. JPEG/TIFF readers expose their EXIF IFD from
    the container header through getexif().
    """
    if image.format == "PNG":
        exif_bytes = image.info.get("exif")
        if not exif_bytes:
            return None
        exif = Image.Exif()
        try:
            exif.load(exif_bytes)
        except (OSError, TypeError, ValueError, SyntaxError) as exc:
            raise ValueError("PNG EXIF orientation metadata is invalid") from exc
        orientation = exif.get(274)
    else:
        try:
            orientation = image.getexif().get(274)
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("Image EXIF orientation metadata is invalid") from exc
    if orientation is None:
        return None
    try:
        orientation = int(orientation)
    except (TypeError, ValueError) as exc:
        raise ValueError("Image EXIF orientation value is invalid") from exc
    if orientation not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise ValueError("Image EXIF orientation value is outside the TIFF range")
    return orientation


def inspect_image(path: Path, *, orient: bool = False) -> tuple[tuple[int, int], str, dict]:
    """Read dimensions/mode/print metadata without decoding customer pixels."""
    path = Path(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            opener = PngImagePlugin.PngImageFile if path.suffix.lower() == ".png" else Image.open
            with opener(path) as image:
                width, height = image.size
                if orient:
                    orientation = _header_exif_orientation(image)
                    if orientation in (5, 6, 7, 8):
                        width, height = height, width
                return (width, height), image.mode, {
                    key: image.info[key] for key in ("icc_profile", "dpi")
                    if key in image.info
                }
    except Image.DecompressionBombError:
        image = _open_vips(path, autorot=orient)
        try:
            return (image.width, image.height), _vips_mode(image), _fallback_metadata(image)
        finally:
            image = None


def _check_cancel(cancel_check) -> None:
    if cancel_check and cancel_check():
        raise InterruptedError("Processing stopped by user")


def _watch_vips(image, progress_callback, cancel_check, low: int, high: int, label: str) -> None:
    image.set_progress(True)

    def evaluate(current, info):
        if cancel_check and cancel_check():
            current.set_kill(True)
            return
        if progress_callback:
            value = low + round((high - low) * info.percent / 100)
            progress_callback(value, label)

    image.signal_connect("eval", evaluate)


def _copy_v2_metadata(image, v2_image):
    image = image.copy(xres=v2_image.xres, yres=v2_image.yres)
    profile = _vips_profile(v2_image)
    if profile:
        # ICC profile data is a VipsBlob metadata item, not an optional
        # argument to the libvips "copy" operation. Attach it with the exact
        # metadata GType so pngsave preserves the accepted V2 profile bytes.
        import pyvips
        image.set_type(pyvips.GValue.blob_type, "icc-profile-data", bytes(profile))
    else:
        try:
            image.remove("icc-profile-data")
        except Exception:
            pass
    return image


def prepare_native_2x_inputs_streamed(
    source: Path,
    baseline: Path,
    work_dir: Path,
    *,
    resize_mode: str = "stretch",
    cancel_check=None,
    progress_callback=None,
):
    """Create half-target seed and even-padded V2 reference without Pillow decode."""
    from .large_image import vips
    from tools.v211_four_engine_fusion import (
        MAX_STREAMED_PIXELS,
        MAX_STREAMED_ROW_BYTES,
    )
    from tools.v211_four_engine_tiled_inference import _required_disk_bytes

    source, baseline, work_dir = map(Path, (source, baseline, work_dir))
    source_size, source_mode, source_metadata = inspect_image(source, orient=True)
    target_size, target_mode, metadata = inspect_image(baseline)
    if source_mode not in ("RGB", "RGBA") or target_mode not in ("RGB", "RGBA"):
        raise ValueError("large four-engine source and V2 must be RGB/RGBA")
    if source_metadata.get("icc_profile") != metadata.get("icc_profile"):
        raise ValueError(
            "large four-engine source and accepted V2 ICC profiles differ; "
            "keep the approved V2 output without auxiliary fusion"
        )
    if resize_mode not in ("fit", "stretch"):
        raise ValueError("resize_mode must be 'fit' or 'stretch'")

    padded_size = (
        target_size[0] + target_size[0] % 2,
        target_size[1] + target_size[1] % 2,
    )
    seed_size = (padded_size[0] // 2, padded_size[1] // 2)
    if min(seed_size) < 64:
        raise ValueError("large native tile seed dimensions must be at least 64 pixels")

    channels = 4 if target_mode == "RGBA" else 3
    target_pixels = padded_size[0] * padded_size[1]
    source_pixels = source_size[0] * source_size[1]
    row_bytes = padded_size[0] * channels
    if target_pixels > MAX_STREAMED_PIXELS or source_pixels > MAX_STREAMED_PIXELS:
        raise RuntimeError("large four-engine image exceeds the safe disk-streaming pixel limit")
    if row_bytes > MAX_STREAMED_ROW_BYTES:
        raise RuntimeError("large four-engine target row exceeds the safe streaming buffer limit")

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_target_bytes = row_bytes * padded_size[1]
    raw_seed_bytes = seed_size[0] * seed_size[1] * channels
    # Reserve the native runner's complete candidate/fusion workspace plus
    # both streamed seed/reference files before writing either one.
    required = _required_disk_bytes(raw_target_bytes) + raw_seed_bytes + raw_target_bytes
    if shutil.disk_usage(work_dir).free < required:
        raise OSError("insufficient disk space for large four-engine seed and fusion workspace")

    _check_cancel(cancel_check)
    pyvips = vips()
    source_image = _open_vips(source, autorot=True)
    v2_image = _open_vips(baseline)
    seed_rgb = None
    v2_padded = None
    seed = None
    reference_path = work_dir / "v2_reference_native_2x.png"
    seed_path = work_dir / "native_2x_seed.png"
    try:
        if (source_image.width, source_image.height) != source_size:
            raise ValueError("libvips source orientation/dimensions differ from the image header")
        if (v2_image.width, v2_image.height) != target_size:
            raise ValueError("libvips V2 dimensions differ from the image header")
        if _vips_mode(source_image) != source_mode or _vips_mode(v2_image) != target_mode:
            raise ValueError("libvips source/V2 colour mode differs from the image header")

        padded_width, padded_height = padded_size
        if padded_size != target_size:
            v2_padded = v2_image.embed(
                0, 0, padded_width, padded_height, extend="copy"
            )
        else:
            v2_padded = v2_image

        source_rgb = source_image.extract_band(0, n=3)
        source_width, source_height = source_size
        seed_width, seed_height = seed_size
        if resize_mode == "stretch":
            seed_rgb = source_rgb.resize(
                seed_width / source_width,
                vscale=seed_height / source_height,
                kernel="lanczos3",
            )
        else:
            factor = min(seed_width / source_width, seed_height / source_height)
            contained_width = max(1, min(seed_width, round(source_width * factor)))
            contained_height = max(1, min(seed_height, round(source_height * factor)))
            contained = source_rgb.resize(
                contained_width / source_width,
                vscale=contained_height / source_height,
                kernel="lanczos3",
            )
            background_bytes = v2_padded.crop(0, 0, 1, 1).write_to_memory()
            # pyvips versions differ in whether a one-pixel memory view
            # iterates as integers or one-byte objects. Normalize explicitly
            # to the numeric array expected by vips_embed(background=...).
            background = [
                int(value[0]) if isinstance(value, (bytes, bytearray)) else int(value)
                for value in list(background_bytes)[:3]
            ]
            if len(background) != 3:
                raise ValueError("could not read the accepted V2 fit background colour")
            seed_rgb = contained.embed(
                (seed_width - contained_width) // 2,
                (seed_height - contained_height) // 2,
                seed_width,
                seed_height,
                extend="background",
                background=background,
            )

        if (seed_rgb.width, seed_rgb.height) != seed_size:
            raise ValueError("libvips did not create the exact half-target seed geometry")
        if target_mode == "RGBA":
            alpha = v2_padded.extract_band(3).resize(0.5, kernel="lanczos3")
            seed = seed_rgb.bandjoin(alpha)
        else:
            seed = seed_rgb
        if (seed.width, seed.height) != seed_size:
            raise ValueError("large native seed alpha/geometry mismatch")

        seed = _copy_v2_metadata(seed, v2_padded)
        v2_padded = _copy_v2_metadata(v2_padded, v2_image)
        _watch_vips(v2_padded, progress_callback, cancel_check, 1, 4, "Prepare V2 tile reference")
        _watch_vips(seed, progress_callback, cancel_check, 4, 10, "Prepare large native seed")
        v2_padded.pngsave(str(reference_path), compression=6, interlace=False)
        _check_cancel(cancel_check)
        seed.pngsave(str(seed_path), compression=6, interlace=False)
        _check_cancel(cancel_check)
        return seed_path, reference_path, target_size, padded_size, source_size, metadata
    except Exception:
        reference_path.unlink(missing_ok=True)
        seed_path.unlink(missing_ok=True)
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user") from None
        raise
    finally:
        seed = None
        seed_rgb = None
        v2_padded = None
        v2_image = None
        source_image = None


def save_cropped_png_streamed(
    candidate: Path,
    destination: Path,
    *,
    target_size: tuple[int, int],
    padded_size: tuple[int, int],
    mode: str,
    metadata: dict,
    cancel_check=None,
) -> None:
    """Crop a large padded candidate through libvips rows and stream a QA PNG."""
    from .large_image import vips
    from tools.v211_four_engine_fusion import (
        MAX_STREAMED_PIXELS,
        MAX_STREAMED_ROW_BYTES,
        _write_streamed_png,
    )

    candidate, destination = Path(candidate), Path(destination)
    width, height = target_size
    channels = 4 if mode == "RGBA" else 3
    row_bytes = width * channels
    if width < 1 or height < 1 or width * height > MAX_STREAMED_PIXELS:
        raise ValueError("large four-engine QA crop exceeds the safe streaming pixel limit")
    if row_bytes > MAX_STREAMED_ROW_BYTES:
        raise ValueError("large four-engine QA crop row exceeds the safe streaming buffer limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    required_disk = row_bytes * height * 3 + 64 * 1024 * 1024
    if shutil.disk_usage(destination.parent).free < required_disk:
        raise OSError("insufficient disk space for streamed four-engine QA crop")
    _check_cancel(cancel_check)

    image = _open_vips(candidate)
    region = None
    temporary = destination.with_name(
        ".v211_streamed_crop_" + uuid4().hex + ".png"
    )
    created_destination = False
    try:
        if (image.width, image.height) != padded_size:
            raise ValueError("large four-engine candidate dimensions differ from the padded V2 canvas")
        if _vips_mode(image) != mode:
            raise ValueError("large four-engine candidate mode differs from the accepted V2")
        region = vips().Region.new(image)
        with tempfile.TemporaryFile(mode="w+b", dir=destination.parent) as raw:
            raw.truncate(row_bytes * height)
            rows_per_fetch = max(1, min(16, (8 * 1024 * 1024) // row_bytes))
            for y in range(0, height, rows_per_fetch):
                _check_cancel(cancel_check)
                rows = min(rows_per_fetch, height - y)
                block = region.fetch(0, y, width, rows)
                if len(block) != row_bytes * rows:
                    raise ValueError("libvips returned an incomplete QA crop block")
                raw.seek(y * row_bytes)
                raw.write(block)
            _write_streamed_png(
                raw, temporary, target_size, mode, metadata, cancel_check
            )
        _check_cancel(cancel_check)
        with temporary.open("rb") as source_stream, destination.open("xb") as target_stream:
            created_destination = True
            while True:
                _check_cancel(cancel_check)
                block = source_stream.read(1024 * 1024)
                if not block:
                    break
                target_stream.write(block)
    except Exception:
        if created_destination:
            destination.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
        region = None
        image = None
