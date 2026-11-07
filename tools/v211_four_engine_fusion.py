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
from typing import Callable
import math
import os
import shutil
import struct
import tempfile
import warnings
import zlib

import numpy as np
from PIL import Image, ImageFilter, PngImagePlugin

from tools.v211_four_engine_coordinator import ENGINES

# Conservative detail weights: 3 Windows-verified favourite models dominate.
WEIGHTS = {"real_esrgan": 0.37, "waifu2x": 0.28, "real_cugan": 0.35}
ANIME4K_DETAIL_WEIGHT = 0.06
TILE = 384
# RGB fusion writes a raw disk-backed raster and then streams PNG scanlines.
# The cap is a practical disk/output bound, not an in-memory allocation limit.
MAX_STREAMED_PIXELS = 1_000_000_000
MAX_STREAMED_ROW_BYTES = 64 * 1024 * 1024
MAX_RGBA_VALIDATION_PIXELS = 18_000_000
PNG_IDAT_CHUNK_BYTES = 1024 * 1024
HALO = 8
MAX_DETAIL_CHANGE = 6.0


def _png_pixel_count_from_header(path: Path) -> int:
    """Read only the PNG signature/IHDR; never decode a large print master."""
    with Path(path).open("rb") as stream:
        header = stream.read(33)
    if (len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n"
            or int.from_bytes(header[8:12], "big") != 13
            or header[12:16] != b"IHDR"):
        raise ValueError("V2 reference must be a valid RGB/RGBA PNG")
    expected_crc = int.from_bytes(header[29:33], "big")
    if (zlib.crc32(header[12:29]) & 0xFFFFFFFF) != expected_crc:
        raise ValueError("V2 PNG IHDR checksum is invalid")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width < 1 or height < 1:
        raise ValueError("V2 PNG dimensions are invalid")
    return width * height


def _image_pixel_count_from_header(path: Path) -> int:
    """Inspect image dimensions without decoding pixel data."""
    path = Path(path)
    if path.suffix.lower() == ".png":
        return _png_pixel_count_from_header(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                return image.width * image.height
    except Image.DecompressionBombError:
        return MAX_STREAMED_PIXELS + 1


MAX_PNG_HEADER_SCAN_BYTES = 32 * 1024 * 1024
MAX_PNG_HEADER_CHUNK_BYTES = 16 * 1024 * 1024
MAX_PNG_ICC_BYTES = 16 * 1024 * 1024


def _read_png_header(path: Path) -> tuple[int, int, str, dict]:
    """Read bounded PNG header metadata without invoking Pillow's pixel decoder.

    Pillow enforces its process-wide decompression-bomb ceiling even when only
    PngImageFile metadata is requested. Large customer masters therefore use
    this small header reader and libvips regions; no global Pillow setting is
    changed and no customer raster is decoded here.
    """
    path = Path(path)
    with path.open("rb") as stream:
        if stream.read(8) != b"\\x89PNG\\r\\n\\x1a\\n":
            raise ValueError("PNG signature is invalid")
        scanned = 8
        width = height = None
        mode = None
        info: dict = {}
        saw_ihdr = saw_iccp = saw_phys = False
        while True:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise ValueError("PNG ended before its first IDAT chunk")
            length = int.from_bytes(chunk_header[:4], "big")
            kind = chunk_header[4:8]
            if kind == b"IDAT":
                if not saw_ihdr:
                    raise ValueError("PNG IDAT precedes IHDR")
                return int(width), int(height), str(mode), info
            if length > MAX_PNG_HEADER_CHUNK_BYTES:
                raise ValueError("PNG pre-IDAT metadata chunk exceeds the safe header limit")
            scanned += 12 + length
            if scanned > MAX_PNG_HEADER_SCAN_BYTES:
                raise ValueError("PNG metadata before IDAT exceeds the safe header scan limit")
            payload = stream.read(length)
            crc_bytes = stream.read(4)
            if len(payload) != length or len(crc_bytes) != 4:
                raise ValueError("PNG metadata chunk is truncated")
            checksum = zlib.crc32(kind)
            checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
            if checksum != int.from_bytes(crc_bytes, "big"):
                raise ValueError("PNG metadata chunk CRC is invalid")

            if not saw_ihdr:
                if kind != b"IHDR" or length != 13:
                    raise ValueError("PNG must begin with a 13-byte IHDR chunk")
                width = int.from_bytes(payload[0:4], "big")
                height = int.from_bytes(payload[4:8], "big")
                bit_depth, color_type, compression, filtering, interlace = payload[8:13]
                if width < 1 or height < 1:
                    raise ValueError("PNG dimensions are invalid")
                if (bit_depth != 8 or color_type not in (2, 6)
                        or compression != 0 or filtering != 0 or interlace not in (0, 1)):
                    raise ValueError("large four-engine PNG must be 8-bit RGB/RGBA")
                mode = "RGBA" if color_type == 6 else "RGB"
                saw_ihdr = True
                continue

            if kind == b"IHDR":
                raise ValueError("PNG contains duplicate IHDR metadata")
            if kind == b"iCCP":
                if saw_iccp:
                    raise ValueError("PNG contains duplicate ICC profiles")
                separator = payload.find(b"\\x00")
                if separator < 1 or separator > 79 or separator + 2 > len(payload):
                    raise ValueError("PNG ICC profile header is invalid")
                if payload[separator + 1] != 0:
                    raise ValueError("PNG ICC compression method is unsupported")
                decompressor = zlib.decompressobj()
                compressed = payload[separator + 2:]
                profile = decompressor.decompress(compressed, MAX_PNG_ICC_BYTES + 1)
                if len(profile) > MAX_PNG_ICC_BYTES or decompressor.unconsumed_tail:
                    raise ValueError("PNG ICC profile exceeds the safe metadata limit")
                tail = decompressor.flush()
                if (len(profile) + len(tail) > MAX_PNG_ICC_BYTES
                        or not decompressor.eof or decompressor.unused_data):
                    raise ValueError("PNG ICC profile stream is invalid or oversized")
                info["icc_profile"] = profile + tail
                saw_iccp = True
            elif kind == b"pHYs":
                if saw_phys or length != 9:
                    raise ValueError("PNG pHYs metadata is invalid or duplicated")
                x_ppm = int.from_bytes(payload[0:4], "big")
                y_ppm = int.from_bytes(payload[4:8], "big")
                unit = payload[8]
                if unit == 1:
                    if x_ppm < 1 or y_ppm < 1:
                        raise ValueError("PNG print resolution metadata is invalid")
                    info["dpi"] = (x_ppm * 0.0254, y_ppm * 0.0254)
                elif unit != 0:
                    raise ValueError("PNG pHYs unit is invalid")
                saw_phys = True
            elif kind == b"IEND":
                raise ValueError("PNG ended before image data")
            

class _PngHeaderImage:
    """Pillow-compatible metadata shell for a large PNG; pixels stay in libvips."""

    def __init__(self, path: Path, header: tuple[int, int, str, dict]):
        self.path = Path(path)
        self.width, self.height, self.mode, info = header
        self.size = (self.width, self.height)
        self.info = dict(info)
        self.format = "PNG"

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def _open_fusion_image(path: Path):
    """Open small rasters with Pillow and large PNGs through header + libvips.

    The metadata shell deliberately has no pixel decoder. Every pixel read for
    large images must go through _FusionRaster's bounded pyvips Region.fetch.
    """
    path = Path(path)
    if path.suffix.lower() == ".png":
        header = _read_png_header(path)
        if header[0] * header[1] > MAX_RGBA_VALIDATION_PIXELS:
            return _PngHeaderImage(path, header)
        return PngImagePlugin.PngImageFile(path)
    return Image.open(path)


class _FusionRaster:
    """Metadata-first raster with sequential libvips crops for large PNGs."""

    def __init__(self, path: Path, *, use_vips: bool, image=None):
        self.path = Path(path)
        self._owns_image = image is None
        self.image = image if image is not None else _open_fusion_image(self.path)
        self._vips = None
        self._region = None
        if use_vips:
            if self.path.suffix.lower() != ".png":
                if self._owns_image:
                    self.image.close()
                raise RuntimeError(
                    "large disk-backed fusion currently requires PNG source, V2 and candidates"
                )
            try:
                import pyvips
                self._vips = pyvips.Image.new_from_file(
                    str(self.path), access="random", fail_on="error",
                    unlimited=True,
                )
                expected_bands = 4 if self.image.mode == "RGBA" else 3
                if (self._vips.width, self._vips.height) != self.image.size:
                    raise ValueError("libvips and PNG header dimensions differ")
                if self._vips.format != "uchar" or self._vips.bands != expected_bands:
                    raise ValueError("large fusion PNG must decode as 8-bit RGB/RGBA")
                self._region = pyvips.Region.new(self._vips)
            except Exception as exc:
                self._vips = None
                self._region = None
                if self._owns_image:
                    self.image.close()
                if isinstance(exc, (ValueError, RuntimeError)):
                    raise
                raise RuntimeError(
                    "pyvips random-access PNG regions are required for RGB fusion above 18 MP"
                ) from exc

    def crop(self, box: tuple[int, int, int, int]) -> Image.Image:
        if self._region is None:
            return self.image.crop(box)
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        pixels = self._region.fetch(left, top, width, height)
        expected = width * height * (4 if self.image.mode == "RGBA" else 3)
        if len(pixels) != expected:
            raise ValueError("libvips returned an incomplete fusion tile")
        return Image.frombytes(self.image.mode, (width, height), pixels)

    def close(self) -> None:
        self._region = None
        self._vips = None
        if self._owns_image:
            self.image.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def _validate_fusion_candidate(
    source: Path,
    v2_reference: Path,
    candidate: Path,
    target_size: tuple[int, int],
    *,
    use_vips: bool,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """Validate a candidate against the accepted V2 raster, including tiled alpha.

    V2 is the alpha master: a research candidate must carry exactly the same
    target-resolution alpha as the accepted V2 reference. Comparing to V2
    avoids re-resizing the source alpha in a second, potentially different
    resampler. Large RGBA checks use libvips regions and never decode the
    complete customer raster through Pillow.
    """
    with ExitStack() as stack:
        original = stack.enter_context(_open_fusion_image(source))
        output = stack.enter_context(_open_fusion_image(candidate))
        base = stack.enter_context(_open_fusion_image(v2_reference))
        if output.size != target_size:
            raise ValueError("candidate dimensions differ from target")
        if original.mode not in ("RGB", "RGBA") or output.mode != original.mode:
            raise ValueError("candidate changed image mode or transparency")
        if base.size != target_size or base.mode != original.mode:
            raise ValueError("accepted V2 mode or dimensions differ from candidate")
        if (original.info.get("icc_profile") != output.info.get("icc_profile")
                or base.info.get("icc_profile") != output.info.get("icc_profile")):
            raise ValueError("candidate lost or altered ICC profile")

        if original.mode == "RGBA":
            base_reader = stack.enter_context(
                _FusionRaster(v2_reference, use_vips=use_vips, image=base)
            )
            candidate_reader = stack.enter_context(
                _FusionRaster(candidate, use_vips=use_vips, image=output)
            )
            width, height = target_size
            for y in range(0, height, TILE):
                for x in range(0, width, TILE):
                    if cancel_check and cancel_check():
                        raise InterruptedError("Processing stopped by user")
                    w, h = min(TILE, width - x), min(TILE, height - y)
                    box = (x, y, x + w, y + h)
                    expected_alpha = np.asarray(
                        base_reader.crop(box).getchannel("A"), dtype=np.uint8
                    )
                    actual_alpha = np.asarray(
                        candidate_reader.crop(box).getchannel("A"), dtype=np.uint8
                    )
                    if not np.array_equal(expected_alpha, actual_alpha):
                        raise ValueError(
                            "candidate alpha differs from accepted V2 alpha; "
                            "transparent edges cannot be used for fusion"
                        )


def _write_png_chunk(stream, kind: bytes, payload: bytes) -> None:
    if len(kind) != 4:
        raise ValueError("PNG chunk type must contain four bytes")
    stream.write(len(payload).to_bytes(4, "big"))
    stream.write(kind)
    stream.write(payload)
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum)
    stream.write((checksum & 0xFFFFFFFF).to_bytes(4, "big"))


def _verify_streamed_png(path: Path, expected_size: tuple[int, int]) -> None:
    """Verify PNG chunk order, lengths and CRCs without decoding the raster."""
    with Path(path).open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("streamed fusion output has an invalid PNG signature")
        saw_ihdr = False
        saw_idat = False
        saw_iend = False
        while True:
            length_bytes = stream.read(4)
            if len(length_bytes) != 4:
                raise ValueError("streamed fusion output ended before IEND")
            length = int.from_bytes(length_bytes, "big")
            kind = stream.read(4)
            if len(kind) != 4:
                raise ValueError("streamed fusion output has a truncated chunk type")
            if not saw_ihdr and kind != b"IHDR":
                raise ValueError("streamed fusion output does not start with IHDR")
            checksum = zlib.crc32(kind)
            if kind == b"IHDR":
                if saw_ihdr or length != 13:
                    raise ValueError("streamed fusion output has an invalid IHDR")
                payload = stream.read(length)
                if len(payload) != length:
                    raise ValueError("streamed fusion output has a truncated IHDR")
                if (int.from_bytes(payload[0:4], "big"),
                        int.from_bytes(payload[4:8], "big")) != expected_size:
                    raise ValueError("streamed fusion output dimensions changed")
                checksum = zlib.crc32(payload, checksum)
                saw_ihdr = True
            else:
                remaining = length
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError("streamed fusion output has a truncated chunk")
                    checksum = zlib.crc32(block, checksum)
                    remaining -= len(block)
                if kind == b"IDAT":
                    saw_idat = True
                elif kind == b"IEND":
                    if length != 0:
                        raise ValueError("streamed fusion output has a non-empty IEND")
                    saw_iend = True
            crc_bytes = stream.read(4)
            if len(crc_bytes) != 4 or (checksum & 0xFFFFFFFF) != int.from_bytes(crc_bytes, "big"):
                raise ValueError("streamed fusion output chunk CRC mismatch")
            if saw_iend:
                if not saw_idat or stream.read(1):
                    raise ValueError("streamed fusion output has invalid trailing data")
                break
        if not saw_ihdr or not saw_idat or not saw_iend:
            raise ValueError("streamed fusion output is incomplete")


def _write_streamed_png(
    raw, output: Path, size: tuple[int, int], mode: str,
    metadata: dict, cancel_check: Callable[[], bool] | None,
) -> None:
    """Encode a disk-backed RGB/RGBA raster as PNG with bounded row memory."""
    width, height = size
    channels = 4 if mode == "RGBA" else 3
    row_bytes = width * channels
    expected_bytes = row_bytes * height
    raw.seek(0, os.SEEK_END)
    if raw.tell() < expected_bytes:
        raise ValueError("disk-backed fusion raster is incomplete")

    fd, temporary_name = tempfile.mkstemp(
        suffix=".png", prefix=".v211_fusion_", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as stream:
            stream.write(b"\x89PNG\r\n\x1a\n")
            color_type = 6 if mode == "RGBA" else 2
            ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
            _write_png_chunk(stream, b"IHDR", ihdr)

            profile = metadata.get("icc_profile")
            if profile:
                profile_bytes = bytes(profile)
                iccp = b"NiyomSilp ICC\x00\x00" + zlib.compress(profile_bytes, 6)
                _write_png_chunk(stream, b"iCCP", iccp)

            dpi = metadata.get("dpi")
            if dpi is not None:
                if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                    dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
                else:
                    dpi_x = dpi_y = float(dpi)
                if (math.isfinite(dpi_x) and math.isfinite(dpi_y)
                        and dpi_x > 0 and dpi_y > 0):
                    ppm_x = int(round(dpi_x / 0.0254))
                    ppm_y = int(round(dpi_y / 0.0254))
                    if 0 < ppm_x <= 0xFFFFFFFF and 0 < ppm_y <= 0xFFFFFFFF:
                        _write_png_chunk(
                            stream, b"pHYs",
                            struct.pack(">IIB", ppm_x, ppm_y, 1),
                        )

            compressor = zlib.compressobj(level=6)
            pending = bytearray()
            for y in range(height):
                if y % 16 == 0 and cancel_check and cancel_check():
                    raise InterruptedError("Processing stopped by user")
                raw.seek(y * row_bytes)
                row = raw.read(row_bytes)
                if len(row) != row_bytes:
                    raise ValueError("disk-backed fusion raster row is incomplete")
                pending.extend(compressor.compress(b"\x00" + row))
                while len(pending) >= PNG_IDAT_CHUNK_BYTES:
                    payload = bytes(pending[:PNG_IDAT_CHUNK_BYTES])
                    del pending[:PNG_IDAT_CHUNK_BYTES]
                    _write_png_chunk(stream, b"IDAT", payload)
            pending.extend(compressor.flush())
            while pending:
                payload = bytes(pending[:PNG_IDAT_CHUNK_BYTES])
                del pending[:PNG_IDAT_CHUNK_BYTES]
                _write_png_chunk(stream, b"IDAT", payload)
            _write_png_chunk(stream, b"IEND", b"")

        _verify_streamed_png(temporary, size)
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


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
    cancel_check: Callable[[], bool] | None = None,
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
    # Preflight every raster from its container header before Pillow crop/load.
    # A small V2 target must not accidentally admit a huge source or stale
    # candidate into the full-image validation path.
    input_labels = [
        ("source", source),
        ("V2 reference", v2_reference),
        *((name + " candidate", Path(candidates[name])) for name in ENGINES),
    ]
    for label, path in input_labels:
        pixels = _image_pixel_count_from_header(path)
        if pixels > MAX_STREAMED_PIXELS:
            raise RuntimeError(
                "Four-engine fusion " + label + " exceeds the safe disk-streaming "
                "limit; use the approved V2 large-image pipeline. The accepted "
                "V2 image has not been modified."
            )
    protected_regions = tuple(protected_regions)

    with ExitStack() as stack:
        base = stack.enter_context(_open_fusion_image(v2_reference))
        if base.format != "PNG" or base.mode not in ("RGB", "RGBA"):
            raise ValueError("V2 reference must be RGB/RGBA PNG")
        W, H = base.size
        channels = 4 if base.mode == "RGBA" else 3
        row_bytes = W * channels
        if row_bytes > MAX_STREAMED_ROW_BYTES:
            raise RuntimeError(
                "Four-engine fusion row exceeds the safe streaming buffer limit; "
                "use the approved V2 large-image pipeline."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        raw_bytes = row_bytes * H
        required_disk_bytes = raw_bytes * 2 + 16 * 1024 * 1024
        if shutil.disk_usage(output.parent).free < required_disk_bytes:
            raise RuntimeError(
                "Insufficient free disk space for atomic disk-backed four-engine fusion."
            )
        with _open_fusion_image(source) as original:
            if not any((W, H) == (original.width * scale, original.height * scale) for scale in (2, 4)):
                raise ValueError("four-engine fusion requires exact 2x or 4x dimensions")
        metadata = {key: base.info[key] for key in ("icc_profile", "dpi") if key in base.info}
        # Above the Pillow validation threshold, every source/candidate/V2
        # pixel access must go through bounded libvips regions, for RGB and RGBA.
        use_vips = W * H > MAX_RGBA_VALIDATION_PIXELS
        for engine in ENGINES:
            _validate_fusion_candidate(
                source, v2_reference, Path(candidates[engine]), (W, H),
                use_vips=use_vips, cancel_check=cancel_check,
            )
        base_reader = stack.enter_context(
            _FusionRaster(v2_reference, use_vips=use_vips, image=base)
        )
        raw = stack.enter_context(
            tempfile.TemporaryFile(mode="w+b", dir=output.parent)
        )
        raw.truncate(raw_bytes)
        images = {}
        for engine in ENGINES:
            reader = stack.enter_context(
                _FusionRaster(Path(candidates[engine]), use_vips=use_vips)
            )
            if (reader.image.mode != base.mode
                    or reader.image.info.get("icc_profile") != metadata.get("icc_profile")):
                raise ValueError(engine + ": mode or ICC differs from accepted V2")
            # Normalized ICC is a necessity; DPI will be taken from V2.
            images[engine] = reader
        # Validate all rectangles, including when face preservation is bypassed.
        _protected_mask(0, 0, 1, 1, (W, H), protected_regions)
        mean_delta_sum = 0.0
        edge_pixels = 0
        effective_contributions = {name: 0.0 for name in ENGINES}
        effective_pixel_counts = {name: 0 for name in ENGINES}
        total_pixels = W * H
        # Two-dimensional libvips Region.fetch keeps both axes bounded; Pillow
        # is used only for small images where a full decode stays under 18 MP.
        for y in range(0, H, TILE):
            for x in range(0, W, TILE):
                if cancel_check and cancel_check():
                    raise InterruptedError("Processing stopped by user")
                w, h = min(TILE, W - x), min(TILE, H - y)
                xx, yy = max(0, x - HALO), max(0, y - HALO)
                xx2, yy2 = min(W, x + w + HALO), min(H, y + h + HALO)
                box = (xx, yy, xx2, yy2)
                base_region = base_reader.crop(box)
                base_rgb = np.asarray(base_region.convert("RGB"), dtype=np.float32)
                center = (slice(y - yy, y - yy + h), slice(x - xx, x - xx + w))
                base_c = base_rgb[center]
                base_hp = _gray_highpass(base_region)[center]
                # Preserve V2 RGB beneath transparent and antialiased cutout
                # boundaries. Exact alpha alone is not enough: changing hidden
                # RGB at partially transparent pixels can create fringes when
                # downstream print/layout software resamples the PNG.
                alpha_tile = (
                    np.asarray(
                        base_region.crop((x - xx, y - yy, x - xx + w, y - yy + h)).getchannel("A"),
                        dtype=np.uint8,
                    )
                    if base.mode == "RGBA" else None
                )
                if preserve_all_v2_faces:
                    terms = {name: np.zeros((h, w), dtype=np.float32) for name in ENGINES}
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
                    # Keep each model's exact weighted term so we can measure
                    # whether removing that model changes final RGB pixels.
                    terms = {
                        name: (0.56 * WEIGHTS[name] * diff[name])
                        for name in WEIGHTS
                    }
                    anime = diff["anime4k"]
                    anime_agrees = (np.sign(anime) == np.sign(core)) & (np.abs(anime) <= 9.0)
                    terms["anime4k"] = ANIME4K_DETAIL_WEIGHT * np.where(
                        anime_agrees, anime, 0.0
                    )
                    edge_gate &= ~_protected_mask(x, y, w, h, (W, H), protected_regions)
                    if alpha_tile is not None:
                        # Only fully opaque V2 pixels may receive new detail;
                        # semi-transparent edge pixels remain bit-identical.
                        edge_gate &= alpha_tile == 255
                    terms = {
                        name: np.where(edge_gate, term, 0.0)
                        for name, term in terms.items()
                    }

                combined_terms = sum(terms.values(), np.zeros((h, w), dtype=np.float32))
                delta = np.clip(combined_terms, -MAX_DETAIL_CHANGE, MAX_DETAIL_CHANGE)
                delta = np.where(edge_gate, delta, 0.0)

                # Shared luminance must fit every RGB channel; clipping channels
                # independently shifts hue at saturated print edges.
                upward = np.min(255.0 - base_c, axis=2)
                downward = np.min(base_c, axis=2)
                safe_delta = np.minimum(np.maximum(delta, -downward), upward)
                rgb = np.rint(base_c + safe_delta[..., None]).astype("uint8")

                # Counterfactual attribution: for each engine, recompute the
                # final RGB tile with only that engine's term removed. Count a
                # contribution only where the quantized output pixel actually
                # changes after edge gating, luminance clipping and rounding.
                # This is stronger than counting candidate files or raw weights.
                for name, term in terms.items():
                    without_delta = np.clip(
                        combined_terms - term, -MAX_DETAIL_CHANGE, MAX_DETAIL_CHANGE
                    )
                    without_delta = np.where(edge_gate, without_delta, 0.0)
                    without_safe = np.minimum(
                        np.maximum(without_delta, -downward), upward
                    )
                    without_rgb = np.rint(
                        base_c + without_safe[..., None]
                    ).astype("uint8")
                    pixel_effect = np.any(rgb != without_rgb, axis=2)
                    effective_pixel_counts[name] += int(pixel_effect.sum())
                    effective_contributions[name] += float(
                        np.abs(rgb.astype("int16") - without_rgb.astype("int16")).sum()
                    )
                if base.mode == "RGBA":
                    # Alpha is copied unchanged from V2; prevents fringe and
                    # satisfies PSD/AI transparent print workflow.
                    output_array = np.dstack((rgb, alpha_tile))
                else:
                    output_array = rgb
                for row_index in range(h):
                    raw.seek(((y + row_index) * W + x) * channels)
                    raw.write(output_array[row_index].tobytes())
                edge_pixels += int(edge_gate.sum())
                mean_delta_sum += float(np.abs(safe_delta).sum())
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        raw.flush()
        # The full-size raster remains on disk; only one PNG scanline and a
        # bounded IDAT buffer are resident while the atomic QA file is encoded.
        _write_streamed_png(raw, output, (W, H), base.mode, metadata, cancel_check)

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
            name: round(value / max(1, total_pixels * 3), 6)
            for name, value in effective_contributions.items()
        },
        "engine_pixel_effect_pixels": effective_pixel_counts,
        "engine_pixel_effect_verified": {
            name: count > 0 for name, count in effective_pixel_counts.items()
        },
        "all_four_engine_pixels_contributed": all(
            effective_pixel_counts[name] > 0 for name in ENGINES
        ),
        "contribution_attribution": (
            "leave_one_engine_out_final_rgb_pixel_difference_after_gating_clipping_and_rounding"
        ),
        "output": str(output),
        "quality_certified": False,
        "experimental_preview_only": True,
    }
