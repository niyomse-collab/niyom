"""NiyomSilp independent desktop pipeline for an isolated Windows TEST build.

Uses independently authored NiyomSilp Real-ESRGAN wrapper, print output layer
and optional portrait-module hook. Does NOT call ARM's EngineManager/adapter.
The existing GUI source and installed main application are unmodified.
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from independent_core.engine import CoreConfig, IndependentCore
from independent_core.icc_external_export import export_selected_cmyk
from independent_core.print_output import PrintSpec, export_print_image, fit_rgb_to_print

MODEL_FILENAME = "RealESRGAN_x4plus.pth"


def runtime_root() -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DeviceView:
    name: str
    device_id: str
    backend: str
    memory_mb: int | None = None


class DesktopTestAdapter:
    """Drop-in UI contract with a NiyomSilp-owned AI dispatch and print path."""

    def __init__(self):
        self.ai = self
        self._engine = None
        self.zip_icc_sha256: str | None = None
        self._device = None

    @property
    def model_path(self) -> Path:
        return runtime_root() / "models" / MODEL_FILENAME

    @property
    def available(self) -> bool:
        return self.model_path.is_file()

    def default_device(self) -> DeviceView:
        if self._device is None:
            # CUDA preferred, otherwise CPU; *never* fall back to a fake upscaler.
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                self._device = DeviceView(torch.cuda.get_device_name(0), "cuda:0",
                                          "CUDA", int(props.total_memory / 1024**2))
            else:
                self._device = DeviceView("CPU", "cpu", "CPU")
        return self._device

    def _get_engine(self) -> IndependentCore:
        if self._engine is None:
            dev = self.default_device()
            if not self.available:
                raise FileNotFoundError(f"Missing real AI model: {self.model_path}")
            self._engine = IndependentCore(CoreConfig(
                model_path=self.model_path, device=dev.device_id,
                tile=256, tile_pad=10, pre_pad=0, fp16=False))
        return self._engine

    @staticmethod
    def _cancelled(callback) -> None:
        if callback and callback():
            raise InterruptedError("Stopped by user")

    def process(self, input_path, output_path, settings,
                progress=None, cancel=None, use_ai=True) -> dict:
        src, dest = Path(input_path), Path(output_path)
        if src.resolve() == dest.resolve():
            raise ValueError("Cannot replace the input file")
        if dest.exists():
            raise FileExistsError(f"TEST output already exists; refusing overwrite: {dest}")
        self._cancelled(cancel)
        with Image.open(src) as im:
            original_size = im.size
        if settings.print_width and settings.print_height:
            target = PrintSpec(dpi=settings.dpi, width=settings.print_width,
                               height=settings.print_height, unit=settings.print_unit).target_pixels()
            required = max(target[0] / original_size[0], target[1] / original_size[1])
            factor = 2 if required <= 2 else (4 if required <= 4 else 8)
        else:
            factor = int(settings.ai_scale)
            target = (original_size[0] * factor, original_size[1] * factor)
        if max(target) > 30000:
            raise ValueError("Image exceeds 30,000 pixel per-side output limit")
        if progress:
            progress(3, "NiyomSilp TEST - prepare")
        if not use_ai or factor <= 1:
            with Image.open(src) as im:
                output = ImageOps.exif_transpose(im).convert("RGB")
        else:
            self._cancelled(cancel)
            if not self.available:
                raise FileNotFoundError("RealESRGAN_x4plus model unavailable")
            with tempfile.TemporaryDirectory(prefix="niyomsil_core_test_") as td:
                temp_png = Path(td) / "ai.png"
                callback = lambda v: progress(8 + round(v * 0.74), "NiyomSilp Core AI") if progress else None
                self._get_engine().enhance(
                    src, temp_png, scale=factor, progress_callback=callback,
                    cancel_check=cancel)
                with Image.open(temp_png) as im:
                    output = im.convert("RGB").copy()
        self._cancelled(cancel)
        if progress:
            progress(84, "Fit to print dimensions")
        output = fit_rgb_to_print(output, target)

        face_data = {
            "enabled": bool(getattr(settings, "face_protection", False)),
            "applied": False, "face_count": 0,
            "mode": getattr(settings, "face_mode", "protect"),
            "strength": int(getattr(settings, "face_strength", 35)),
            "skipped_reason": None,
        }
        if use_ai and face_data["enabled"]:
            try:
                from signprint_ai.face_module import FaceProtectionModule
                device_id = self.default_device().device_id
                def face_progress(value, description):
                    if progress:
                        progress(85 + round(9 * max(0, min(100, value)) / 100), description)
                enhanced, result = FaceProtectionModule().apply(
                    output, device_name=device_id, mode=face_data["mode"],
                    strength=face_data["strength"], progress=face_progress, cancel=cancel)
                output = enhanced
                face_data = result.as_dict()
            except InterruptedError:
                raise
            except Exception as exc:
                face_data["skipped_reason"] = f"Face Protect skipped: {exc}"
        self._cancelled(cancel)
        if progress:
            progress(94, "Saving NiyomSilp TEST output")

        if settings.color_mode.upper() == "CMYK" and str(settings.icc_profile_path or "").lower().endswith(".zip"):
            if not self.zip_icc_sha256:
                raise ValueError("Select one CMYK ICC from ZIP using the ICC button")
            export_selected_cmyk(
                output, dest, settings.icc_profile_path,
                self.zip_icc_sha256, dpi=settings.dpi)
        else:
            export_print_image(output, dest, PrintSpec(
                dpi=settings.dpi, color_mode=settings.color_mode,
                icc_profile=settings.icc_profile_path))
        self._cancelled(cancel)
        if progress:
            progress(100, "NiyomSilp TEST completed")

        return {
            "input": str(src), "output": str(dest),
            "original_size": original_size, "output_size": output.size,
            "ai_available": self.available, "ai_scale": factor, "dpi": settings.dpi,
            "device": self.default_device().name, "engine": "NiyomSilp Independent Core TEST",
            "face_protection": face_data,
        }
