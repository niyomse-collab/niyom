from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageOps

from app.engine.engine_manager import EngineManager
from .processing import EnhanceSettings, print_pixels, save_image
from .face_module import FaceProtectionModule

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]


class ARMCoreAdapter:
    """Compatibility adapter for the tested ARM V2.2.8 PyTorch/CUDA core.

    The AI path is intentionally the same as the proven v1-arm-core build:
      - ARM DeviceManager
      - ARM EngineManager
      - ARM RealESRGANEngine
      - RealESRGAN_x4plus.pth
      - CUDA tile=256 / FP32 when NVIDIA CUDA is available
      - 8x = 4x pass + 2x pass
      - no extra denoise/contrast/sharpen filters

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
            root = Path(__file__).resolve().parents[1]
            candidates = [
                root / "models" / "RealESRGAN_x4plus.pth",
                root / "_internal" / "models" / "RealESRGAN_x4plus.pth",
            ]
            return any(p.is_file() for p in candidates)
        except Exception:
            return False

    def default_device(self):
        return self.engine_manager.device_manager.get_default_device()

    def available_devices(self):
        """Return detected execution devices without modifying ARM Core."""
        return list(self.engine_manager.device_manager.get_devices())

    def resolve_device(self, device_id: str | None):
        requested = (device_id or "AUTO").strip()
        if requested.upper() == "AUTO":
            return self.engine_manager.device_manager.get_default_device()
        selected = self.engine_manager.device_manager.get_device(requested)
        if selected is None:
            raise RuntimeError(f"ไม่พบ Device: {requested}")
        return selected

    def detect_faces(self, input_path: str | Path) -> list[dict]:
        """Upload-time face scan.

        Use CPU deliberately so auto-detection can run without competing for the
        CUDA device that may already be busy with the ARM render worker.
        """
        return self.face_module.detect_faces(input_path, device_name="cpu")

    @staticmethod
    def _model_scale_for_dimensions(width: int, height: int, target_size: tuple[int, int]) -> int:
        required = max(target_size[0] / width, target_size[1] / height)
        return 2 if required <= 2 else (4 if required <= 4 else 8)

    @staticmethod
    def _map_face_targets_to_output(
        source_size: tuple[int, int],
        target_size: tuple[int, int],
        targets: tuple[tuple[float, float], ...],
    ) -> tuple[tuple[float, float], ...]:
        """Map normalized source face centers through ImageOps.contain + canvas.

        The ARM core pixels remain untouched; this only keeps the user's face
        selection aligned when the requested print canvas has a different
        aspect ratio from the uploaded image.
        """
        if not targets:
            return ()
        sw, sh = source_size
        tw, th = target_size
        if sw <= 0 or sh <= 0 or tw <= 0 or th <= 0:
            return tuple(targets)

        scale = min(tw / sw, th / sh)
        rendered_w = sw * scale
        rendered_h = sh * scale
        offset_x = (tw - rendered_w) / 2.0
        offset_y = (th - rendered_h) / 2.0

        mapped = []
        for x, y in targets:
            px = (float(x) * sw * scale + offset_x) / tw
            py = (float(y) * sh * scale + offset_y) / th
            mapped.append(
                (
                    max(0.0, min(1.0, px)),
                    max(0.0, min(1.0, py)),
                )
            )
        return tuple(mapped)

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

        with Image.open(src) as im:
            source_size = im.size

        if settings.print_width and settings.print_height:
            target_size = print_pixels(
                settings.print_width,
                settings.print_height,
                settings.print_unit,
                settings.dpi,
            )
            model_scale = self._model_scale_for_dimensions(
                source_size[0], source_size[1], target_size
            )
        else:
            model_scale = int(settings.ai_scale)
            target_size = (
                source_size[0] * model_scale,
                source_size[1] * model_scale,
            )

        if max(target_size) > 30000:
            raise ValueError(
                "ขนาดด้านใดด้านหนึ่งเกิน 30,000 px ตามข้อจำกัดของ ARM V2.2.8 Core"
            )

        if progress:
            progress(2, "Prepare / Analyze")

        if not use_ai or model_scale <= 1:
            with Image.open(src) as im:
                output = ImageOps.exif_transpose(im).convert("RGB")
        else:
            requested_device = getattr(settings, "device_id", "AUTO") or "AUTO"
            engine = self.engine_manager.create_engine(requested_device)

            with tempfile.TemporaryDirectory(prefix="niyomsil_arm_core_") as td:
                td = Path(td)
                final_ai = td / "arm_final.png"

                if model_scale == 8:
                    stage4 = td / "arm_4x.png"
                    if progress:
                        progress(10, "ARM Real-ESRGAN · pass 1/2 · 4x")
                    engine.enhance(
                        src,
                        stage4,
                        scale=4,
                        progress_callback=self._mapped_progress(
                            progress, 12, 48, "ARM Real-ESRGAN · pass 1/2 · 4x"
                        ),
                        cancel_check=cancel,
                    )
                    if cancel and cancel():
                        raise InterruptedError("Processing stopped by user")
                    if progress:
                        progress(48, "ARM Real-ESRGAN · pass 2/2 · 2x")
                    engine.enhance(
                        stage4,
                        final_ai,
                        scale=2,
                        progress_callback=self._mapped_progress(
                            progress, 48, 82, "ARM Real-ESRGAN · pass 2/2 · 2x"
                        ),
                        cancel_check=cancel,
                    )
                else:
                    if model_scale not in (2, 4):
                        raise ValueError("ARM Core รองรับ AI Scale 2x / 4x / 8x")
                    if progress:
                        progress(10, f"ARM Real-ESRGAN · {model_scale}x")
                    engine.enhance(
                        src,
                        final_ai,
                        scale=model_scale,
                        progress_callback=self._mapped_progress(
                            progress, 12, 82, f"ARM Real-ESRGAN · {model_scale}x"
                        ),
                        cancel_check=cancel,
                    )

                with Image.open(final_ai) as im:
                    output = im.convert("RGB").copy()

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        # Exact final-size behavior from the tested ARM V1 flow.
        if output.size != target_size:
            if progress:
                progress(86, f"Final Resize · {target_size[0]:,} × {target_size[1]:,}")
            contained = ImageOps.contain(
                output,
                target_size,
                method=Image.Resampling.LANCZOS,
            )
            canvas = Image.new("RGB", target_size, "white")
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

        # Optional face layer: disabled means the exact proven ARM output above
        # flows directly to Save Output unchanged.
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
                selected_device = self.resolve_device(
                    getattr(settings, "device_id", "AUTO")
                )
                device_id = getattr(selected_device, "device_id", "cpu")

                def face_progress(value, message):
                    if progress:
                        progress(88 + round(6 * max(0, min(100, value)) / 100), message)

                raw_targets = tuple(getattr(settings, "face_targets", ()) or ())
                mapped_targets = self._map_face_targets_to_output(
                    source_size,
                    target_size,
                    raw_targets,
                )
                protected, face_result = self.face_module.apply(
                    output,
                    device_name=device_id,
                    mode=face_info["mode"],
                    strength=face_info["strength"],
                    selected_targets=mapped_targets,
                    gentle_finish=bool(getattr(settings, "portrait_gentle", False)),
                    progress=face_progress,
                    cancel=cancel,
                )
                output = protected
                face_info = face_result.as_dict()
            except InterruptedError:
                raise
            except Exception as exc:
                # Face Protection is optional by design. If it fails, keep the
                # exact ARM result instead of failing or altering the job.
                face_info["skipped_reason"] = f"Face Protect ข้ามการทำงาน: {exc}"
                if progress:
                    progress(94, "Face Protect ข้าม — ใช้ผล ARM Core เดิม")

        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        if progress:
            progress(96 if face_info["enabled"] else 94, "Save Output")

        dst.parent.mkdir(parents=True, exist_ok=True)

        # RGB PNG stays pixel-identical to the final ARM result. CMYK/ICC and
        # alternate file formats are export-only operations after AI processing.
        if settings.color_mode.upper() == "RGB" and dst.suffix.lower() == ".png":
            output.save(
                dst,
                format="PNG",
                dpi=(settings.dpi, settings.dpi),
                compress_level=3,
            )
        else:
            save_image(
                np.asarray(output),
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
            "dpi": settings.dpi,
            "device": device_name,
            "engine": "ARM V2.2.8 / RealESRGAN_x4plus (PyTorch)",
            "face_protection": face_info,
        }
