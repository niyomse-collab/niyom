"""V2 disk-backed image processing; no application pixel-count ceiling.

Small jobs retain the validated Pillow/core path. Large jobs use libvips for
streaming decode/resize/export and disk rasters between bounded AI tiles.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import math
import gc
import os
import shutil
import tempfile
import warnings

import numpy as np
from PIL import Image, ImageOps

IN_MEMORY_PIXELS = 16_000_000
VIPS_MAX_COORD = 2**31 - 1  # libvips image header uses signed 32-bit coordinates.
JPEG_MAX_SIDE = 65_500  # libjpeg encoder constraint, not a processing limit.
TIFF_BIG_THRESHOLD_BYTES = 3_500_000_000


@lru_cache(maxsize=1)
def vips():
    os.environ.setdefault("VIPS_DISC_THRESHOLD", "64m")
    try:
        import pyvips
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "ไม่พบส่วนประมวลผลภาพใหญ่ กรุณาติดตั้งชุด v2 ที่มี pyvips[binary]"
        ) from exc
    pyvips.cache_set_max(0)
    pyvips.cache_set_max_mem(64 * 1024 * 1024)
    pyvips.concurrency_set(2)
    return pyvips


def check_cancel(cancel):
    if cancel and cancel():
        raise InterruptedError("Processing stopped by user")


def failure_info(exc):
    # Native-library tracebacks can retain an operation and its open files.
    # Store only error data, then release the traceback before Windows cleanup.
    cls = type(exc) if isinstance(exc, (InterruptedError, OSError, ValueError, RuntimeError)) else RuntimeError
    return cls, str(exc)


def raise_failure(failure, cancel):
    check_cancel(cancel)
    cls, message = failure
    raise cls(message) from None


def parse_scale(value) -> int:
    text = str(value).strip().lower().removesuffix("x")
    try:
        scale = int(text)
    except (ValueError, OverflowError) as exc:
        raise ValueError("อัตราขยายต้องเป็นจำนวนเต็มบวก เช่น 4x, 8x หรือ 16x") from exc
    if scale < 1:
        raise ValueError("อัตราขยายต้องเป็นจำนวนเต็มบวก")
    return scale


def validate_target_size(size):
    if len(size) != 2 or any(not isinstance(n, int) or n < 1 for n in size):
        raise ValueError("ขนาดปลายทางต้องเป็นจำนวนพิกเซลเต็มบวก")
    if max(size) > VIPS_MAX_COORD:
        raise ValueError("ขนาดด้านภาพเกินช่วงตัวเลขที่ระบบไฟล์ภาพรองรับ")


def validate_export(path, size, settings):
    validate_target_size(size)
    if not math.isfinite(settings.dpi) or settings.dpi <= 0:
        raise ValueError("DPI ต้องเป็นค่าบวกที่มีขอบเขต")
    suffix = Path(path).suffix.lower()
    if suffix not in (".png", ".tif", ".tiff", ".jpg", ".jpeg", ".pdf"):
        raise ValueError("กรุณาเลือก PNG, TIFF, JPG หรือ PDF")
    if suffix in (".jpg", ".jpeg") and max(size) > JPEG_MAX_SIDE:
        raise ValueError(
            "รูปแบบ JPG รองรับด้านภาพไม่เกิน 65,500 px "
            "กรุณาเลือก PNG, TIFF หรือ PDF เพื่อคงพิกเซลและ DPI ตามที่ตั้ง"
        )
    if settings.color_mode.upper() == "CMYK":
        if suffix == ".png":
            raise ValueError("PNG ไม่รองรับ CMYK กรุณาเลือก TIFF, JPG หรือ PDF")
        if not settings.icc_profile_path or not Path(settings.icc_profile_path).is_file():
            raise ValueError("โหมด CMYK ต้องเลือกไฟล์ ICC/ICM Profile ที่มีอยู่จริง")


def open_vips(path, *, access="sequential"):
    # PNG/TIFF decoder security ceilings are inappropriate for explicitly
    # selected print masters. Other loaders do not all expose 'unlimited'.
    options = {"access": access, "fail_on": "error"}
    if Path(path).suffix.lower() in (".png", ".tif", ".tiff"):
        options["unlimited"] = True
    return vips().Image.new_from_file(str(path), **options).autorot()


def as_rgb(image):
    image = image.colourspace("srgb")
    if image.bands > 3:
        # Match the existing V2 RGB conversion (alpha is not part of its output).
        image = image.extract_band(0, n=3)
    return image.cast("uchar")


def image_size(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                size = image.size
                if image.getexif().get(274) in (5, 6, 7, 8):
                    size = size[::-1]
                return size
    except Image.DecompressionBombError:
        image = open_vips(path)
        return image.width, image.height


def needs_streaming(source_size, target_size, model_scale=1):
    source_pixels = math.prod(source_size)
    # RealESRGANer allocates a whole 4x tensor even for an outscale=2 pass.
    inference_pixels = source_pixels * (64 if model_scale == 8 else 16 if model_scale > 1 else 1)
    return max(source_pixels, math.prod(target_size), inference_pixels) > IN_MEMORY_PIXELS


def output_size_summary(source_size, target_size, model_scale=1):
    """Inform the operator without introducing a new pixel-count limit.

    The uncompressed RGB estimate describes one image buffer, not peak RAM or
    disk usage. Multi-pass AI can require several temporary disk rasters.
    """
    validate_target_size(target_size)
    pixels = math.prod(target_size)
    raw_gib = pixels * 3 / (1024 ** 3)
    mode = ("แบ่งส่วนประมวลผลบนดิสก์" if needs_streaming(
        source_size, target_size, model_scale) else "ประมวลผลในหน่วยความจำ")
    return (
        f"ขนาดพิกเซลปลายทาง: {target_size[0]:,} × {target_size[1]:,} px"
        f" • {pixels / 1_000_000:,.1f} MP"
        f" • RGB ดิบประมาณ {raw_gib:,.2f} GiB/ภาพ"
        f" • {mode}"
    )


PREVIEW_BACKGROUND = (23, 23, 23)


def composite_preview_rgba(image):
    """Show transparent artwork over the same neutral matte in both UI paths."""
    if "A" not in image.getbands() and "transparency" not in image.info:
        return image.convert("RGB")
    foreground = image.convert("RGBA")
    background = Image.new("RGBA", foreground.size, PREVIEW_BACKGROUND + (255,))
    return Image.alpha_composite(background, foreground).convert("RGB")


def thumbnail(path, box=(1600, 1600)):
    size = image_size(path)
    if math.prod(size) <= IN_MEMORY_PIXELS:
        with Image.open(path) as raw:
            image = composite_preview_rgba(ImageOps.exif_transpose(raw))
            image.thumbnail(box, Image.Resampling.LANCZOS)
            return image
    source = open_vips(path)
    image = as_rgb(source)
    has_alpha = bool(source.hasalpha())
    if has_alpha:
        # Resample premultiplied channels; invisible RGB cannot tint an edge.
        alpha = source.extract_band(source.bands - 1).cast("uchar")
        image = image.bandjoin(alpha).copy(interpretation="srgb").premultiply()
    scale = min(1.0, box[0] / image.width, box[1] / image.height)
    image = image.resize(scale, kernel="lanczos3") if scale < 1 else image
    if has_alpha:
        image = image.unpremultiply().flatten(background=list(PREVIEW_BACKGROUND)).cast("uchar")
    return to_pillow(image)


def to_pillow(image):
    return Image.frombytes("RGB", (image.width, image.height), image.write_to_memory())


def watch(image, progress, cancel, lo, hi, label):
    last = [-1]
    image.set_progress(True)

    def evaluate(current, info):
        if cancel and cancel():
            current.set_kill(True)
            return
        value = lo + round((hi - lo) * info.percent / 100)
        if progress and value != last[0]:
            last[0] = value
            progress(value, label)

    image.signal_connect("eval", evaluate)


def ensure_disk(path, required):
    if shutil.disk_usage(path).free < required:
        raise OSError(
            f"พื้นที่ดิสก์ไม่พอสำหรับข้อมูลระหว่างทำงาน ต้องการอย่างน้อย "
            f"{required / 1024**3:.2f} GB โดยยังคงขนาดภาพและ DPI เดิม"
        )


def read_raster(path, size):
    image = open_vips(path, access="random")
    if (image.width, image.height) != size or image.bands != 3:
        raise RuntimeError("ข้อมูลภาพระหว่างทำงานมีขนาดไม่ตรงตามคำขอ")
    return image


def make_source_raster(src, raw_path, progress, cancel):
    image = as_rgb(open_vips(src))
    size = image.width, image.height
    tile_width = max(16, min(256, math.ceil(size[0]/16)*16))
    tile_height = max(16, min(256, math.ceil(size[1]/16)*16))
    storage = math.ceil(size[0]/tile_width)*math.ceil(size[1]/tile_height)*tile_width*tile_height*3
    ensure_disk(raw_path.parent, storage)
    check_cancel(cancel)
    watch(image, progress, cancel, 2, 10, "อ่านภาพใหญ่ลงดิสก์")
    failure = None
    try:
        image.tiffsave(str(raw_path), compression="none", tile=True,
                       tile_width=tile_width, tile_height=tile_height, bigtiff=True)
    except Exception as exc:
        failure = failure_info(exc)
    finally:
        image = None
    if failure:
        gc.collect()
        raise_failure(failure, cancel)
    check_cancel(cancel)
    return size


def upscale_raster(src, dst, size, scale, engine, progress, cancel, lo, hi, *,
                   refine_edges=False, protected_regions=None, refine_settings=None,
                   alpha_source=None, refine_alpha_source=None):
    import tifffile

    # Refine only the final AI pass, on padded image tiles BEFORE cropping.
    # The source alpha mask is streamed separately and is never touched here.
    if refine_edges:
        from .v2_graphic_edges import refine_sign_edges

    refine_kwargs = {"settings": refine_settings} if refine_settings is not None else {}
    width, height = size
    target = width * scale, height * scale
    validate_target_size(target)
    tile = engine.upsampler.tile_size or 256
    pad = engine.upsampler.tile_pad
    if hasattr(engine, "enhance_graphic_tile"):
        pad = max(pad, math.ceil(64 / scale))
    if refine_edges and refine_settings is not None:
        # Geometry has 32 output pixels of finite context, also at 2x.
        pad = max(pad, math.ceil(32 / scale))
    tile_width = max(16, min(tile*scale, math.ceil(target[0]/16)*16))
    tile_height = max(16, min(tile*scale, math.ceil(target[1]/16)*16))
    storage = math.ceil(target[0]/tile_width)*math.ceil(target[1]/tile_height)*tile_width*tile_height*3
    ensure_disk(dst.parent, storage)
    source = read_raster(src, size)
    region = vips().Region.new(source)
    # Only the first AI pass sees the original PNG alpha. Keep a bounded
    # source-alpha region alongside the RGB source for each padded tile.
    input_with_alpha = open_vips(alpha_source, access="random") if alpha_source else None
    source_alpha = (input_with_alpha.extract_band(input_with_alpha.bands - 1).cast("uchar")
                    if input_with_alpha is not None and input_with_alpha.hasalpha() else None)
    alpha_region = vips().Region.new(source_alpha) if source_alpha is not None else None

    refinement_alpha = None
    refinement_alpha_region = None
    if refine_edges and refine_alpha_source:
        alpha_image = open_vips(refine_alpha_source, access="random")
        if alpha_image.hasalpha():
            refinement_alpha = resize_image(
                alpha_image.extract_band(alpha_image.bands - 1).cast("uchar"),
                target, "stretch", background=[0])
            refinement_alpha_region = vips().Region.new(refinement_alpha)

    def tiles():
        total = math.ceil(width / tile) * math.ceil(height / tile)
        completed = 0
        for y in range(0, height, tile):
            for x in range(0, width, tile):
                check_cancel(cancel)
                x2, y2 = min(width, x + tile), min(height, y + tile)
                left, top = max(0, x - pad), max(0, y - pad)
                right, bottom = min(width, x2 + pad), min(height, y2 + pad)
                pixels = np.frombuffer(region.fetch(left,top,right-left,bottom-top),
                                       dtype="uint8").reshape(bottom-top,right-left,3).copy()
                if alpha_region is not None:
                    from .v2_alpha_edges import bleed_transparent_rgb
                    a = np.frombuffer(
                        alpha_region.fetch(left, top, right-left, bottom-top),
                        dtype="uint8"
                    ).reshape(bottom-top, right-left).copy()
                    pixels = bleed_transparent_rgb(pixels, a)
                if hasattr(engine, "enhance_graphic_tile"):
                    protected_tile = tuple(
                        ((x1*width-left)/(right-left), (y1*height-top)/(bottom-top),
                         (x2*width-left)/(right-left), (y2*height-top)/(bottom-top))
                        for x1,y1,x2,y2 in protected_regions or ()
                        if x2*width>left and x1*width<right and y2*height>top and y1*height<bottom)
                    enhanced = engine.enhance_graphic_tile(pixels, scale, cancel, protected_tile)
                else:
                    enhanced = engine.enhance_tile(pixels, scale, cancel)
                expected = ((bottom - top) * scale, (right - left) * scale, 3)
                if enhanced.shape != expected or enhanced.dtype != np.uint8:
                    raise RuntimeError("AI ส่งขนาดหรือชนิดข้อมูลของส่วนภาพไม่ตรงตามคำขอ")
                if refine_edges:
                    # Refine on the padded tile, then crop so boundaries do
                    # not introduce separate sharpening lines or gaps.
                    padded = Image.fromarray(enhanced, "RGB")
                    if refinement_alpha_region is not None:
                        alpha_pixels = np.frombuffer(refinement_alpha_region.fetch(
                            left * scale, top * scale,
                            (right-left) * scale, (bottom-top) * scale), dtype="uint8"
                        ).reshape((bottom-top)*scale, (right-left)*scale).copy()
                        padded.putalpha(Image.fromarray(alpha_pixels))
                    if protected_regions:
                        # Source-normalized face ROIs map into each padded tile's
                        # own image coordinates. Avoid touching restored faces.
                        tile_faces = tuple(
                            ((x1 * width - left) / (right - left),
                             (y1 * height - top) / (bottom - top),
                             (x2 * width - left) / (right - left),
                             (y2 * height - top) / (bottom - top))
                            for x1, y1, x2, y2 in protected_regions
                            if x2 * width > left and x1 * width < right
                            and y2 * height > top and y1 * height < bottom
                        )
                        padded = refine_sign_edges(
                            padded, protected_regions=tile_faces, **refine_kwargs
                        ) if tile_faces else refine_sign_edges(padded, **refine_kwargs)
                    else:
                        padded = refine_sign_edges(padded, **refine_kwargs)
                    enhanced = np.asarray(padded.convert("RGB"))
                offset_x, offset_y = (x - left) * scale, (y - top) * scale
                storage_tile = np.zeros((tile_height,tile_width,3),dtype="uint8")
                storage_tile[:(y2-y)*scale, :(x2-x)*scale] = enhanced[
                    offset_y:offset_y+(y2-y)*scale, offset_x:offset_x+(x2-x)*scale]
                del pixels, enhanced
                yield storage_tile
                completed += 1
                if progress:
                    progress(lo + round((hi - lo) * completed / total),
                             f"AI ภาพใหญ่ · ส่วน {completed:,}/{total:,} · {scale}x")
        check_cancel(cancel)
    try:
        with tifffile.TiffWriter(dst, bigtiff=True) as writer:
            writer.write(tiles(), shape=(target[1],target[0],3), dtype="uint8",
                         tile=(tile_height,tile_width), photometric="rgb", metadata=None)
    finally:
        region = None
        source = None
        refinement_alpha_region = None
        refinement_alpha = None
        alpha_region = None
        source_alpha = None
        input_with_alpha = None
    return target


def resize_image(image, size, mode="fit", background=None):
    width, height = size
    if (image.width, image.height) == size:
        return image
    if mode == "stretch":
        contained = size
    elif mode == "fit":
        factor = min(width / image.width, height / image.height)
        contained = (max(1, min(width, round(image.width * factor))),
                     max(1, min(height, round(image.height * factor))))
    else:
        raise ValueError("โหมดปรับขนาดต้องเป็น fit หรือ stretch")
    image = image.resize(contained[0] / image.width,
                         vscale=contained[1] / image.height, kernel="lanczos3")
    if (image.width, image.height) != contained:
        raise RuntimeError("ส่วนปรับขนาดส่งจำนวนพิกเซลไม่ตรงตามคำขอ")
    if contained != size:
        image = image.embed((width - contained[0]) // 2, (height - contained[1]) // 2,
                            width, height, extend="background", background=(background if background is not None else [255] * image.bands))
    return image


def export_image(image, dst, settings, progress, cancel):
    size = image.width, image.height
    validate_export(dst, size, settings)
    check_cancel(cancel)
    profile = None
    if settings.color_mode.upper() == "CMYK":
        profile = str(settings.icc_profile_path)
        image = image.icc_transform(profile, input_profile="srgb", embedded=False, intent="perceptual")
        if image.bands != 4 or image.interpretation != "cmyk":
            raise ValueError("ICC Profile ที่เลือกไม่ใช่โปรไฟล์ CMYK")
    image = image.copy(xres=settings.dpi / 25.4, yres=settings.dpi / 25.4)
    suffix = dst.suffix.lower()
    if suffix != ".pdf":
        watch(image, progress, cancel, 88, 99, "ปรับขนาดและบันทึกภาพใหญ่")
    fd, temporary = tempfile.mkstemp(prefix=".niyomsil_output_", suffix=suffix, dir=dst.parent)
    os.close(fd)
    temporary = Path(temporary)
    failure = None
    try:
        if suffix == ".png":
            image.pngsave(str(temporary), compression=3)
        elif suffix in (".tif", ".tiff"):
            storage = math.ceil(size[0]/256)*math.ceil(size[1]/256)*256*256*image.bands
            image.tiffsave(str(temporary), compression="lzw", tile=True,
                           tile_width=256, tile_height=256,
                           bigtiff=storage >= TIFF_BIG_THRESHOLD_BYTES,
                           resunit="inch")
        elif suffix in (".jpg", ".jpeg"):
            image.jpegsave(str(temporary), Q=96, subsample_mode="off")
        else:
            from .large_pdf import save_pdf
            save_pdf(image, temporary, settings.dpi, profile, progress, cancel)
        check_cancel(cancel)
        os.replace(temporary, dst)
    except Exception as exc:
        failure = failure_info(exc)
    image = None
    if failure:
        gc.collect()
    temporary.unlink(missing_ok=True)
    if failure:
        raise_failure(failure, cancel)


class LazyPreviewSource:
    """Pillow-compatible viewport source that never caches the full print."""
    def __init__(self, path):
        self.path = Path(path)
        self.size = image_size(path)
        self.width, self.height = self.size

    def transform(self, box, method, data, resample=None, fillcolor=(23, 23, 23)):
        step_x, _, left, _, step_y, top = data
        if step_x != step_y:
            raise ValueError("Preview viewport requires uniform scaling")
        scale = 1 / step_x
        margin = max(4, math.ceil(4 / scale))
        x1, y1 = max(0, math.floor(left)-margin), max(0, math.floor(top)-margin)
        x2 = min(self.width, math.ceil(left+box[0]/scale)+margin)
        y2 = min(self.height, math.ceil(top+box[1]/scale)+margin)
        if x2 <= x1 or y2 <= y1:
            return Image.new("RGB", box, fillcolor)
        source = open_vips(self.path, access="random")
        image = as_rgb(source)
        # Large-file previews must show transparency as a neutral dark
        # viewport, not a PNG's arbitrary hidden RGB.  Premultiply before
        # resizing so invisible red/black pixels cannot bleed into text edges.
        has_alpha = bool(source.hasalpha())
        if has_alpha:
            alpha = source.extract_band(source.bands - 1).cast("uchar")
            image = image.bandjoin(alpha).copy(interpretation="srgb").premultiply()
        image = image.crop(x1, y1, x2-x1, y2-y1)
        # Reduce first for Fit view; affine interpolation itself does not
        # antialias a huge reduction and would alias small Thai lettering.
        if scale < .5:
            image = image.resize(scale, kernel="lanczos3")
            affine_scale = 1.0
        else:
            affine_scale = scale
        image = image.affine([affine_scale, 0, 0, affine_scale],
                             interpolate=vips().Interpolate.new("bicubic"),
                             odx=(x1-left)*scale, ody=(y1-top)*scale,
                             oarea=[0, 0, box[0], box[1]],
                             extend="background",
                             background=list(fillcolor) + ([255] if has_alpha else []))
        if has_alpha:
            # Flatten only this viewport, not the full print master.
            image = image.unpremultiply().flatten(background=list(fillcolor)).cast("uchar")
        return to_pillow(image)


def preview_source(path):
    if math.prod(image_size(path)) > IN_MEMORY_PIXELS:
        return LazyPreviewSource(path)
    with Image.open(path) as image:
        return composite_preview_rgba(ImageOps.exif_transpose(image))


def source_declares_alpha(src):
    """Read transparency from PNG/TIFF *headers*, never decode a print master.

    Pillow's image-size bomb guard can reject legitimate 200+ MP vinyl files
    even when only inspecting getbands(). Do not silently skip the alpha safety
    check when that happens. PNG tRNS and TIFF ExtraSamples need checking too.
    """
    path = Path(src)
    suffix = path.suffix.lower()
    if suffix == ".png":
        with path.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Invalid PNG signature")
            if stream.read(4) != b"\x00\x00\x00\r" or stream.read(4) != b"IHDR":
                raise ValueError("Invalid PNG IHDR")
            ihdr = stream.read(13)
            if len(ihdr) != 13:
                raise ValueError("Incomplete PNG IHDR")
            colour_type = ihdr[9]
            if colour_type in (4, 6):
                return True
            if colour_type in (0, 2):
                return False
            if colour_type != 3:
                raise ValueError("Unsupported PNG colour type")
            stream.read(4)  # IHDR CRC
            # Indexed transparency is stored in a tRNS chunk before IDAT.
            # Scan only chunk *headers*, not the IDAT or compressed image.
            for _ in range(1024):
                header = stream.read(8)
                if len(header) != 8:
                    raise ValueError("Incomplete indexed PNG metadata")
                length = int.from_bytes(header[:4], "big")
                kind = header[4:]
                if kind == b"tRNS":
                    return True
                if kind in (b"IDAT", b"IEND"):
                    return False
                stream.seek(length + 4, 1)  # data and CRC, no pixel decoding
            raise ValueError("Indexed PNG has too many metadata chunks")
    if suffix in (".tif", ".tiff"):
        import tifffile  # Already required by the V2 large-image runtime.
        with tifffile.TiffFile(path) as tiff:
            page = tiff.pages[0]
            return any(int(item) in (1, 2) for item in page.extrasamples)
    try:
        with Image.open(path) as header:
            return "A" in header.getbands() or "transparency" in header.info
    except Image.DecompressionBombError as exc:
        # Unknown huge formats must fail safely instead of printing black.
        raise RuntimeError(
            "ไม่สามารถตรวจสอบ Alpha จากส่วนหัวไฟล์ภาพขนาดใหญ่ได้ "
            "หยุดส่งออกเพื่อป้องกันพื้นดำ"
        ) from exc


def prepare_source_alpha_for_export(image, src, target_size, settings, dst):
    """Preserve RGB PNG/TIFF transparency; flatten other formats over white.

    AI operates on RGB only. The source alpha is resized separately so neither
    tile inference nor colour management can silently replace transparency
    with undefined hidden RGB (which often displays as a black backdrop).
    """
    source = open_vips(src, access="random")
    if not source.hasalpha():
        # Fail closed if libvips ever misses source transparency. Read only
        # file headers; a 200+ MP source must not bypass this check because
        # Pillow's decompression-bomb limit rejects a metadata-only open.
        if source_declares_alpha(src):
            raise RuntimeError(
                "ต้นฉบับมี Alpha แต่ตัวอ่านภาพใหญ่ไม่พบช่องโปร่งใส "
                "หยุดส่งออกเพื่อป้องกันพื้นดำใน CMYK"
            )
        return image
    alpha = source.extract_band(source.bands - 1).cast("uchar")
    alpha = resize_image(alpha, target_size, settings.resize_mode, background=[0])
    suffix = Path(dst).suffix.lower()
    if settings.color_mode.upper() == "RGB" and suffix in (".png", ".tif", ".tiff"):
        return image.bandjoin(alpha).copy(interpretation="srgb")

    # For CMYK/JPEG/PDF, explicitly composite RGB against white *before*
    # the CMYK ICC transformation.  A customer sample with zero-alpha black
    # pixels produced near-full ink in transparent areas (C224 M202 Y186 K250).
    # Per-pixel arithmetic prevents hidden RGB reaching ICC conversion and
    # does not require allocating the whole output raster in RAM.
    opacity = alpha.cast("float") / 255.0
    return ((image.cast("float") - 255.0) * opacity + 255.0).cast(
        "uchar"
    ).copy(interpretation="srgb")


def process_large(adapter, src, dst, settings, source_size, target_size,
                  model_scale, progress=None, cancel=None, use_ai=True):
    """Keep the master dimensions exact; temporary rasters live beside output."""
    validate_export(dst, target_size, settings)
    dst.parent.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel)
    engine = adapter.create_job_engine(settings) if use_ai and model_scale > 1 else None
    failure = None
    with tempfile.TemporaryDirectory(prefix=".niyomsil_large_", dir=dst.parent) as folder:
        try:
            face_info = _large_job(adapter, engine, src, dst, settings, target_size,
                                   model_scale, Path(folder), progress, cancel, use_ai)
        except Exception as exc:
            failure = failure_info(exc)
        # End the except block first: its native tracebacks retain locked files.
        if failure:
            gc.collect()
    if failure:
        raise_failure(failure, cancel)
    if progress:
        progress(100, "เสร็จแล้ว")
    return {
        "input": str(src), "output": str(dst), "original_size": source_size,
        "output_size": target_size, "ai_available": adapter.available,
        "ai_scale": model_scale if engine else 1, "requested_ai_scale": settings.ai_scale,
        "dpi": settings.dpi, "device": engine.device_name() if engine else "CPU",
        "engine": "NiyomSilp Design Engine", "model": "RealESRGAN_x4plus" if engine else None,
        "graphic_ai_model": ("RealESRGAN_x4plus_anime_6B" if use_ai and model_scale > 1 and getattr(settings, "graphic_ai", False) and settings.text_graphic_boost > 0 else None),
            "runtime": "PyTorch", "processing_mode": "disk_tiles", "face_protection": face_info,
    }


def _large_job(adapter, engine, src, dst, settings, target_size, model_scale, folder, progress, cancel, use_ai):
    source_raw = folder / "source.tif"
    size = make_source_raster(src, source_raw, progress, cancel)
    current = source_raw
    if engine:
        passes = (4, 2) if model_scale == 8 else (model_scale,)
        for index, scale in enumerate(passes):
            next_raw = folder / f"pass_{index}.tif"
            size = upscale_raster(current, next_raw, size, scale, engine, progress, cancel,
                                  10 + round(72 * index / len(passes)),
                                  10 + round(72 * (index + 1) / len(passes)),
                                  refine_edges=(index == len(passes) - 1),
                                  refine_settings=settings,
                                  refine_alpha_source=src,
                                  alpha_source=(src if index == 0 else None),
                                  protected_regions=(settings.face_regions
                                                     if settings.face_protection else None))
            if current != source_raw:
                current.unlink()
            current = next_raw
    image = None
    try:
        image = read_raster(current, size)
        face_info = {
            "enabled": bool(settings.face_protection), "applied": False, "face_count": 0,
            "mode": settings.face_mode, "strength": settings.face_strength, "skipped_reason": None,
        }
        if use_ai and face_info["enabled"]:
            from .large_faces import apply_faces
            image, face_info = apply_faces(adapter, image, read_raster(source_raw, image_size(src)),
                                           settings, folder, progress, cancel)
        image = resize_image(image, target_size, settings.resize_mode)
        # Preserve RGB TIFF alpha as well as PNG. For CMYK/JPEG/PDF, blend
        # source transparency onto white before export colour conversion.
        image = prepare_source_alpha_for_export(
            image, src, target_size, settings, dst
        )
        export_image(image, dst, settings, progress, cancel)
        return face_info
    finally:
        image = None
