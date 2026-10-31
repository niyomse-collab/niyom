"""V2.1.1 experimental HAT super-resolution engine.

This is a genuinely separate, pretrained HAT image model, not a slider on
the existing Real-ESRGAN model. It requires an explicitly provided and
SHA-256 verified checkpoint and optional Spandrel dependency. It does not
download weights automatically, modify V1, or silently fall back to ESRGAN.
V2 remains the default until quality/rights/packaging acceptance.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageOps

# Specific test checkpoint (upstream name; mirrored checkpoint provenance
# needs independent commercial release clearance before a production installer).
HAT_FILE = "HAT_SRx4_ImageNet-pretrain.pth"
HAT_SHA256 = "4ee053c42461187846dc0e93aa5abd34591c0725a8e044a59000e92ee215e833"


def checkpoint_path() -> Path:
    from .face_module.face_protection import resource_root
    return resource_root() / "models" / "experimental" / HAT_FILE


def validate_checkpoint(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            "V2.1.1 HAT: ไม่พบโมเดล HAT ที่ยืนยันแล้วใน models/experimental/ "
            "โปรดติดตั้งชุดโมเดลทดลองที่ตรวจสอบสิทธิ์แล้วก่อนเลือก HAT"
        )
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != HAT_SHA256:
        raise RuntimeError(
            "V2.1.1 HAT: SHA256 ไม่ตรงกับ checkpoint ที่รับรองสำหรับการทดลอง "
            "(ปฏิเสธการโหลดเพื่อความปลอดภัย)"
        )


def _window_padding(height: int, width: int, window: int = 16) -> tuple[int, int, str]:
    """Return bottom/right padding and a safe mode for a HAT border crop."""
    if height < 1 or width < 1 or window < 1:
        raise ValueError("HAT tile/window dimensions must be positive")
    bottom, right = (-height) % window, (-width) % window
    mode = "reflect" if bottom < height and right < width else "replicate"
    return bottom, right, mode


def _require_scale(scale: int) -> None:
    if scale not in (2, 4):
        raise ValueError("HAT SRx4 ใช้สำหรับ AI Scale 2x หรือ 4x เท่านั้น")


def _downsample_4x(pixels: np.ndarray, scale: int, width: int, height: int):
    _require_scale(scale)
    if pixels.shape[:2] != (height * 4, width * 4):
        raise RuntimeError("HAT returned unexpected 4x dimensions")
    if scale == 4:
        return pixels
    return np.asarray(
        Image.fromarray(pixels, "RGB").resize(
            (width * 2, height * 2), Image.Resampling.LANCZOS
        )
    )


def _validate_prediction_shape(shape, height: int, width: int) -> None:
    """Reject truncated or malformed model output before exporting any pixels."""
    expected = (1, 3, height * 4, width * 4)
    if tuple(shape) != expected:
        raise RuntimeError(
            f"HAT returned tensor shape {tuple(shape)}, expected {expected}; "
            "refusing to export an incomplete image"
        )


class HATModelEngine:
    """Alternative 4x image engine with bounded padded tile inference."""

    def __init__(self, selected):
        path = checkpoint_path()
        validate_checkpoint(path)
        try:
            import torch
            from spandrel import ImageModelDescriptor, ModelLoader
        except ImportError as exc:
            raise RuntimeError(
                "V2.1.1 HAT: ไม่พบ spandrel/PyTorch ในโปรแกรม กรุณาติดตั้งชุด Super AI ให้ครบ"
            ) from exc
        if str(selected.backend).upper() == "DIRECTML":
            raise RuntimeError("V2.1.1 HAT ยังไม่ยืนยันการทำงานกับ DirectML โปรดเลือก CUDA/CPU")
        self.selected = selected
        self.device = torch.device(selected.device_id)
        self.torch = torch
        self.upsampler = SimpleNamespace(tile_size=96, tile_pad=32)
        self.model = ModelLoader().load_from_file(str(path))
        if not isinstance(self.model, ImageModelDescriptor):
            raise RuntimeError("HAT checkpoint is not an image model")
        if (self.model.scale != 4 or self.model.input_channels != 3
                or self.model.output_channels != 3):
            raise RuntimeError("HAT checkpoint must have scale=4 and RGB channels")
        # Check the detected architecture, rather than trusting a filename.
        if str(self.model.architecture.id).upper() != "HAT":
            raise RuntimeError("Expected HAT architecture in checkpoint")
        self.model = self.model.to(self.device).eval()

    def device_name(self):
        return self.selected.name

    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        _require_scale(scale)
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        if pixels.ndim != 3 or pixels.shape[2] != 3 or pixels.dtype != np.uint8:
            raise ValueError("HAT expects uint8 RGB tiles")
        h, w = pixels.shape[:2]
        # HAT uses windowed attention: source dimensions must be multiples of
        # the model window size. Border tiles are frequently not multiples.
        # Pad the *source* tensor, then crop the 4x prediction before optional
        # 2x resampling. Reflection requires padding < the source dimension;
        # use replicate for tiny edge crops instead of crashing.
        pad_h, pad_w, mode = _window_padding(h, w)
        tensor = self.torch.from_numpy(np.ascontiguousarray(pixels)).permute(2, 0, 1)
        tensor = tensor.unsqueeze(0).to(device=self.device, dtype=self.torch.float32) / 255.0
        if pad_h or pad_w:
            import torch.nn.functional as functional
            tensor = functional.pad(tensor, (0, pad_w, 0, pad_h), mode=mode)
        try:
            with self.torch.inference_mode():
                prediction = self.model(tensor)
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower():
                raise RuntimeError(
                    "V2.1.1 HAT: หน่วยความจำไม่พอ; ลด tile_size หรือเลือก GPU "
                    "ที่มี VRAM มากขึ้น (ไม่มีการลดคุณภาพหรือสลับโมเดลอัตโนมัติ)"
                ) from exc
            raise
        _validate_prediction_shape(prediction.shape, h + pad_h, w + pad_w)
        if not bool(self.torch.isfinite(prediction).all()):
            raise RuntimeError("V2.1.1 HAT: โมเดลสร้างค่า NaN/Inf; หยุดส่งออกภาพ")
        prediction = prediction[..., :h * 4, :w * 4]
        out = prediction.squeeze(0).permute(1, 2, 0).detach().float().cpu().numpy()
        result = np.rint(np.clip(out, 0, 1) * 255).astype(np.uint8)
        del prediction, tensor
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        return _downsample_4x(result, scale, w, h)

    def enhance(self, input_path, output_path, scale=4,
                progress_callback=None, cancel_check=None):
        _require_scale(scale)
        destination = Path(output_path)
        with Image.open(input_path) as raw:
            # Apply EXIF orientation before AI and alpha extraction. A phone
            # photo with Orientation=6 otherwise has wrong portrait geometry.
            # The exported raster is already oriented, so do not copy the
            # source EXIF orientation tag into the destination.
            original = ImageOps.exif_transpose(raw)
            # This direct RGB engine must not copy a CMYK ICC profile onto RGB
            # output. The colour-managed CMYK print pipeline is separate.
            if original.mode == "CMYK":
                raise ValueError(
                    "V2.1.1 HAT: CMYK ต้องแปลงสีผ่าน ICC เป็น RGB ก่อนใช้ HAT "
                    "ห้ามคัดลอก CMYK ICC ไปยังผลลัพธ์ RGB"
                )
            # A direct HAT export must not silently flatten transparent PNG/TIFF.
            # Propagate visible colours into hidden RGB before AI upscaling to
            # reduce dark fringes; the actual opacity is resized separately.
            has_alpha = ("A" in original.getbands()
                         or "transparency" in original.info)
            # Reject unsupported alpha output *before* expensive AI inference.
            if has_alpha and destination.suffix.lower() not in (
                    ".png", ".tif", ".tiff"):
                raise ValueError(
                    "V2.1.1 HAT: ภาพโปร่งใสต้องส่งออกเป็น PNG/TIFF เพื่อรักษา alpha"
                )
            if has_alpha:
                from .v2_alpha_edges import bleed_transparent_rgb
                rgba = original.convert("RGBA")
                alpha = np.asarray(rgba.getchannel("A")).copy()
                source = bleed_transparent_rgb(
                    np.asarray(rgba.convert("RGB")), alpha
                )
            else:
                alpha = None
                source = np.asarray(original.convert("RGB"))
            icc = original.info.get("icc_profile")
            dpi = original.info.get("dpi")
        h, w = source.shape[:2]
        out = np.empty((h * scale, w * scale, 3), dtype=np.uint8)
        step, pad = self.upsampler.tile_size, self.upsampler.tile_pad
        total = ((h + step - 1) // step) * ((w + step - 1) // step)
        completed = 0
        for top in range(0, h, step):
            for left in range(0, w, step):
                if cancel_check and cancel_check():
                    raise InterruptedError("Processing stopped by user")
                bottom, right = min(h, top + step), min(w, left + step)
                y0, x0 = max(0, top - pad), max(0, left - pad)
                y1, x1 = min(h, bottom + pad), min(w, right + pad)
                crop = self.enhance_tile(source[y0:y1, x0:x1], scale, cancel_check)
                dy, dx = (top - y0) * scale, (left - x0) * scale
                out[top*scale:bottom*scale, left*scale:right*scale] = crop[
                    dy:dy + (bottom-top)*scale, dx:dx + (right-left)*scale
                ]
                completed += 1
                if progress_callback:
                    progress_callback(round(100 * completed / total))
        destination.parent.mkdir(parents=True, exist_ok=True)
        result_image = Image.fromarray(out, "RGB")
        if alpha is not None:
            upscaled_alpha = Image.fromarray(alpha, "L").resize(
                (w * scale, h * scale), Image.Resampling.LANCZOS
            )
            result_image.putalpha(upscaled_alpha)
        save_options = {}
        if icc:
            save_options["icc_profile"] = icc
        if dpi:
            save_options["dpi"] = dpi
        # Do not destroy an existing print master or leave a half-written file
        # if Pillow, the disk, or a TIFF/PNG encoder fails during final export.
        # A same-directory temporary file permits an atomic replacement.
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{destination.stem}-", suffix=destination.suffix,
            dir=destination.parent,
        )
        os.close(descriptor)
        try:
            result_image.save(temporary, **save_options)
            # A cancellation during the final encode must not replace an
            # existing print master. Keep the temporary file disposable.
            if cancel_check and cancel_check():
                raise InterruptedError("Processing stopped by user")
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {
            "model": "HAT_SRx4_ImageNet-pretrain",
            "device": self.device_name(), "scale": scale,
            "output_size": (w*scale, h*scale), "tiles": completed,
        }
