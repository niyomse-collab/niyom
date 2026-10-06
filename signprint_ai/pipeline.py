from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
import sys

import cv2

from .processing import (
    EnhanceSettings,
    enhance_rgb,
    final_resize,
    load_image,
    print_pixels,
    save_image,
)
from .realesrgan_ncnn import RealESRGANNCNN

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class PrintEnhancementPipeline:
    def __init__(self):
        self.ai = RealESRGANNCNN(app_root())

    def process(
        self,
        input_path: str | Path,
        output_path: str | Path,
        settings: EnhanceSettings,
        progress: ProgressFn = None,
        cancel: CancelFn = None,
        use_ai: bool = True,
    ) -> dict:
        rgb, alpha = load_image(input_path)
        original_h, original_w = rgb.shape[:2]

        if progress:
            progress(1, "โหลดภาพต้นฉบับ")
        rgb = enhance_rgb(rgb, settings, progress, cancel)

        if cancel and cancel():
            raise InterruptedError("Processing cancelled")

        if use_ai and settings.ai_scale > 1:
            if progress:
                progress(48, "เริ่ม AI Upscale")
            rgb = self.ai.upscale_array(rgb, settings.ai_scale, progress, cancel)
            if alpha is not None:
                alpha = cv2.resize(alpha, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LANCZOS4)

        target = None
        if settings.print_width and settings.print_height:
            target = print_pixels(settings.print_width, settings.print_height, settings.print_unit, settings.dpi)
            # Guardrail for accidental enormous allocations; banners can still be
            # large, but 60k px on a side is beyond practical single-image RAM use.
            if target[0] > 60000 or target[1] > 60000:
                raise ValueError("ขนาดพิกเซลปลายทางเกิน 60,000 px ต่อด้าน กรุณาลด DPI หรือขนาดงาน")
            if progress:
                progress(82, f"ปรับขนาดปลายทาง {target[0]:,} × {target[1]:,} px")
            rgb = final_resize(rgb, target)
            if alpha is not None:
                alpha = cv2.resize(alpha, target, interpolation=cv2.INTER_LANCZOS4)

        if progress:
            progress(94, "บันทึกไฟล์")
        save_image(rgb, output_path, dpi=settings.dpi, alpha=alpha)
        if progress:
            progress(100, "เสร็จแล้ว")

        return {
            "input": str(input_path),
            "output": str(output_path),
            "original_size": (original_w, original_h),
            "output_size": (rgb.shape[1], rgb.shape[0]),
            "ai_available": self.ai.available,
            "ai_scale": settings.ai_scale if use_ai else 1,
            "dpi": settings.dpi,
        }
