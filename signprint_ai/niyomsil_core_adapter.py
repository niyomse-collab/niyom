from __future__ import annotations

import os
import math
import tempfile
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageOps

from .independent_core import EngineManager, model_path
from .processing import EnhanceSettings, print_pixels, save_image
from .large_image import image_size, needs_streaming, parse_scale, process_large, validate_export
from .face_module import FaceProtectionModule
from .v2_graphic_edges import refine_sign_edges

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]


class NiyomSilpCoreAdapter:
    """Compatibility adapter for the NiyomSilp independently orchestrated PyTorch/CUDA core.

    The AI processing parameters preserve the previously validated image output:
      - NiyomSilp DeviceManager
      - NiyomSilp EngineManager
      - NiyomSilp RealESRGANEngine
      - RealESRGAN_x4plus.pth
      - CUDA tile=256 / FP32 when NVIDIA CUDA is available
      - 8x = 4x pass + 2x pass
      - V2-only, slider-controlled graphic finishing before face restoration

    This class only adapts the engine to the V2 UI API and preserves the
    existing RGB/CMYK/ICC export stage.
    """

    def __init__(self):
        self.engine_manager = EngineManager()
        self.face_module = FaceProtectionModule()
        # app_v2 historically checks pipeline.ai.available; keep that API.
        self.ai = self

    @property
    def available(self) -> bool:
        try:
            return model_path().is_file()
        except Exception:
            return False

    def default_device(self):
        return self.engine_manager.device_manager.get_default_device()

    @staticmethod
    def _model_scale_for_dimensions(width: int, height: int, target_size: tuple[int, int]) -> int:
        required = max(target_size[0] / width, target_size[1] / height)
        return 2 if required <= 2 else (4 if required <= 4 else 8)

    @staticmethod
    def _mapped_progress(progress: ProgressFn, lo: int, hi: int, label: str):
        def callback(value: int):
            if progress:
                mapped = lo + round((hi - lo) * max(0, min(100, value)) / 100)
                progress(mapped, label)
        return callback

    def process(
        self,
        input_path: str | Path,
        output_path: str | Path,
        settings: EnhanceSettings,
        progress: ProgressFn = None,
        cancel: CancelFn = None,
        use_ai: bool = True,
    ) -> dict:
        src = Path(input_path)
        dst = Path(output_path)

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        source_size = image_size(src)
        if settings.print_width is not None or settings.print_height is not None:
            if (settings.print_width is None or settings.print_height is None or
                    not all(math.isfinite(n) and n > 0 for n in
                            (settings.print_width, settings.print_height, settings.dpi))):
                raise ValueError("กรุณาใส่ความกว้าง ความสูง และ DPI เป็นค่าบวกที่มีขอบเขต")
            try:
                target_size = print_pixels(
                    settings.print_width,
                    settings.print_height,
                    settings.print_unit,
                    settings.dpi,
                )
            except OverflowError as exc:
                raise ValueError("ขนาดงานเกินช่วงตัวเลขที่ระบบไฟล์ภาพรองรับ") from exc
            model_scale = self._model_scale_for_dimensions(
                source_size[0], source_size[1], target_size
            )
        else:
            requested_scale = parse_scale(settings.ai_scale)
            target_size = (
                source_size[0] * requested_scale,
                source_size[1] * requested_scale,
            )
            model_scale = (1 if requested_scale == 1 else
                           self._model_scale_for_dimensions(*source_size, target_size))

        validate_export(dst, target_size, settings)

        if needs_streaming(source_size, target_size, model_scale if use_ai else 1):
            return process_large(self, src, dst, settings, source_size, target_size,
                                 model_scale, progress, cancel, use_ai)

        # Only small images reach Pillow. Large masters must use libvips for
        # RGB and alpha, without allocating a full RGBA canvas or triggering
        # Pillow's decompression-bomb guard on legitimate print files.
        with Image.open(src) as source_image:
            oriented = ImageOps.exif_transpose(source_image)
            has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
            source_alpha = oriented.convert("RGBA").getchannel("A").copy() if has_alpha else None

        if progress:
            progress(2, "Prepare / Analyze")

        if not use_ai or model_scale <= 1:
            with Image.open(src) as im:
                output = ImageOps.exif_transpose(im).convert("RGB")
        else:
            engine = self.engine_manager.create_engine(settings.device)

            with tempfile.TemporaryDirectory(prefix="niyomsil_core_") as td:
                td = Path(td)
                final_ai = td / "core_final.png"

                if model_scale == 8:
                    stage4 = td / "core_4x.png"
                    if progress:
                        progress(10, "NiyomSilp Design Engine · pass 1/2 · 4x")
                    engine.enhance(
                        src,
                        stage4,
                        scale=4,
                        progress_callback=self._mapped_progress(
                            progress, 12, 48, "NiyomSilp Design Engine · pass 1/2 · 4x"
                        ),
                        cancel_check=cancel,
                    )
                    if cancel and cancel():
                        raise InterruptedError("Processing stopped by user")
                    if progress:
                        progress(48, "NiyomSilp Design Engine · pass 2/2 · 2x")
                    engine.enhance(
                        stage4,
                        final_ai,
                        scale=2,
                        progress_callback=self._mapped_progress(
                            progress, 48, 82, "NiyomSilp Design Engine · pass 2/2 · 2x"
                        ),
                        cancel_check=cancel,
                    )
                else:
                    if model_scale not in (2, 4):
                        raise ValueError("NiyomSilp Design Engine รองรับ AI Scale 2x / 4x / 8x")
                    if progress:
                        progress(10, f"NiyomSilp Design Engine · {model_scale}x")
                    engine.enhance(
                        src,
                        final_ai,
                        scale=model_scale,
                        progress_callback=self._mapped_progress(
                            progress, 12, 82, f"NiyomSilp Design Engine · {model_scale}x"
                        ),
                        cancel_check=cancel,
                    )

                with Image.open(final_ai) as im:
                    output = im.convert("RGB").copy()

        if source_alpha is not None:
            output.putalpha(source_alpha.resize(output.size, Image.Resampling.LANCZOS))

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        # Finish graphics before face restoration so successful/failed automatic
        # detection never disables text cleanup. Selected face ROIs are excluded.
        if use_ai and model_scale > 1:
            if progress:
                progress(83, "Refine Text / Graphic Edges")
            output = refine_sign_edges(
                output, settings=settings,
                protected_regions=(settings.face_regions if settings.face_protection else None),
            )

        # Retouch before free resizing: detector and facial geometry see the
        # original aspect ratio. Final resizing transforms the whole image once.
        face_info = {
            "enabled": bool(getattr(settings, "face_protection", False)),
            "applied": False,
            "face_count": 0,
            "mode": getattr(settings, "face_mode", "protect"),
            "strength": int(getattr(settings, "face_strength", 35)),
            "skipped_reason": None,
        }
        if use_ai and face_info["enabled"]:
            try:
                selected_device = (self.engine_manager.device_manager.get_default_device()
                                   if settings.device == "AUTO" else
                                   self.engine_manager.device_manager.get_device(settings.device))
                device_id = getattr(selected_device, "device_id", "cpu")

                def face_progress(value, message):
                    if progress:
                        progress(84 + round(10 * max(0, min(100, value)) / 100), message)

                from .face_module.detection import map_regions
                regions = settings.face_regions
                if regions is not None:
                    regions = map_regions(regions, source_size, output.size, settings.resize_mode)
                protected, face_result = self.face_module.apply(
                    output,
                    device_name=device_id,
                    mode=face_info["mode"],
                    strength=face_info["strength"],
                    regions=regions,
                    source_path=src,
                    source_regions=settings.face_regions,
                    resize_mode=settings.resize_mode,
                    progress=face_progress,
                    cancel=cancel,
                )
                output = protected
                if source_alpha is not None:
                    output = output.convert("RGBA")
                    output.putalpha(source_alpha.resize(output.size, Image.Resampling.LANCZOS))
                face_info = face_result.as_dict()
            except InterruptedError:
                raise
            except Exception as exc:
                # Face Protection is optional by design. If it fails, keep the
                # unmodified core result instead of failing or altering the job.
                face_info["skipped_reason"] = f"Face Protect ข้ามการทำงาน: {exc}"
                if progress:
                    progress(94, "Face Protect ข้าม — ใช้ผลจาก NiyomSilp Design Engine เดิม")

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        # Keep the existing fit behavior when locked; free sizing stretches the image.
        if output.size != target_size:
            if progress:
                progress(95, f"Final Resize · {target_size[0]:,} × {target_size[1]:,}")
            if settings.resize_mode == "stretch":
                output = output.resize(target_size, Image.Resampling.LANCZOS)
            else:
                contained = ImageOps.contain(
                    output,
                    target_size,
                    method=Image.Resampling.LANCZOS,
                )
                canvas = Image.new("RGBA" if source_alpha is not None else "RGB", target_size,
                                   (0, 0, 0, 0) if source_alpha is not None else "white")
                canvas.paste(
                    contained,
                    (
                        (target_size[0] - contained.width) // 2,
                        (target_size[1] - contained.height) // 2,
                    ),
                )
                output = canvas

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        if progress:
            progress(96, "Save Output")

        dst.parent.mkdir(parents=True, exist_ok=True)

        # RGB PNG stays pixel-identical to the final core result. CMYK/ICC and
        # alternate file formats are export-only operations after AI processing.
        if settings.color_mode.upper() == "RGB" and dst.suffix.lower() == ".png":
            output.save(
                dst,
                format="PNG",
                dpi=(settings.dpi, settings.dpi),
                compress_level=3,
            )
        else:
            if output.mode == "RGBA" and dst.suffix.lower() in (".jpg", ".jpeg", ".pdf"):
                flattened = Image.new("RGB", output.size, "white")
                flattened.paste(output, mask=output.getchannel("A"))
                export_pixels = np.asarray(flattened)
            else:
                export_pixels = np.asarray(output)
            save_image(
                export_pixels,
                dst,
                dpi=settings.dpi,
                color_mode=settings.color_mode,
                icc_profile_path=settings.icc_profile_path,
            )

        if progress:
            progress(100, "เสร็จแล้ว")

        device_name = "CPU"
        try:
            if self.engine_manager.engine is not None:
                device_name = self.engine_manager.engine.device_name()
            else:
                device_name = self.engine_manager.device_manager.get_default_device().name
        except Exception:
            pass

        return {
            "input": str(src),
            "output": str(dst),
            "original_size": source_size,
            "output_size": output.size,
            "ai_available": True,
            "ai_scale": model_scale,
            "requested_ai_scale": settings.ai_scale,
            "processing_mode": "memory",
            "dpi": settings.dpi,
            "device": device_name,
            "engine": "NiyomSilp Design Engine",
            "model": "RealESRGAN_x4plus",
            "runtime": "PyTorch",
            "face_protection": face_info,
        }
