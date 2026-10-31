"""Optional NAFNet-GoPro neural deblur BEFORE the unchanged V2 engine.

Unlike SwinIR denoise15, this addresses camera motion/defocus-like blur in
photographs. Intended for visibly blurred *photographic* areas, not exact Thai
glyph reconstruction. Uses the original V2 Real-ESRGAN + GFPGAN afterward.

No weight downloads happen in the app. The specific official GoPro width64
weight must pass a full SHA-256 preflight. The author's code is MIT; the
specific checkpoint's commercial redistribution terms still need clearance.
This experimental mode is OFF by default and never alters V1/V2 stable.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

NAFNET_NAME = "NAFNet-GoPro-width64.pth"
# Cross-referenced with the official-weight evaluation and the HF mirror.
# Not permission to redistribute weights with a commercial installer.
NAFNET_SHA256 = "329d3ab4077b8d6b7ff61de376e483714667960bf85be027bf4335cda701196f"
NAFNET_OFFICIAL_ID = "1S0PVRbyTakYY9a82kujgZLbMihfNBLfC"


def nafnet_checkpoint_path() -> Path:
    from .face_module.face_protection import resource_root
    return resource_root() / "models" / "experimental" / NAFNET_NAME


def verify_nafnet_checkpoint(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("V2.1.1 NAFNet: ไม่พบไฟล์โมเดลลดภาพเบลอ")
    if path.stat().st_size < 50_000_000:
        raise RuntimeError("V2.1.1 NAFNet: checkpoint มีขนาดผิดปกติ")
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    if digest != NAFNET_SHA256:
        raise RuntimeError("V2.1.1 NAFNet: SHA256 ของ checkpoint ไม่ตรงรุ่น")


def blend_photo_deblur(original: np.ndarray, deblurred: np.ndarray,
                       strength: float = .85, protected_regions=()) -> np.ndarray:
    """Restore only photolike signal, protect flat sign ink / face ROIs.

    A large visible difference is NOT evidence of higher print quality.
    Real high-resolution reference and human A/B still decide acceptance.
    """
    if (original.shape != deblurred.shape or original.ndim != 3
            or original.shape[-1] != 3
            or original.dtype != np.uint8 or deblurred.dtype != np.uint8):
        raise ValueError("NAFNet blend requires equal uint8 RGB images")
    if not math.isfinite(strength) or not (0 <= strength <= 1):
        raise ValueError("NAFNet strength must be between 0 and 1")
    if strength == 0:
        return original.copy()

    base = original.astype(np.float32)
    restored = deblurred.astype(np.float32)
    rgb_min = base.min(axis=2)
    rgb_max = base.max(axis=2)
    saturated = (rgb_max-rgb_min > 115) & (rgb_max > 160)
    # A saturated logo has a crisp block outline or uninterrupted flat ink.
    # Protect the complete fill AND its nearby border, not only the centre.
    high_chroma = cv2.dilate(
        saturated.astype(np.uint8), np.ones((7, 7), np.uint8)
    ).astype(bool)
    gray = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY)
    # Protect dark text/graphics including strokes with thin white halos.
    closed = cv2.morphologyEx(
        gray, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8)
    ).astype(np.float32)
    dark_ink = (gray < 100) & ((closed-gray.astype(np.float32)) >= 35)
    dark_ink = cv2.dilate(
        dark_ink.astype(np.uint8), np.ones((7, 7), np.uint8)
    ).astype(bool)

    protected = high_chroma | dark_ink
    h, w = gray.shape
    for region in protected_regions or ():
        if (len(region) != 4 or
                not all(math.isfinite(float(value)) for value in region)):
            raise ValueError("NAFNet protected face ROI must be finite")
        x1, y1, x2, y2 = map(float, region)
        if not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1:
            raise ValueError("NAFNet face regions must be normalized")
        margin = max(4, round(min((x2-x1)*w, (y2-y1)*h)*.15))
        left = max(0, math.floor(x1*w)-margin)
        top = max(0, math.floor(y1*h)-margin)
        right = min(w, math.ceil(x2*w)+margin)
        bottom = min(h, math.ceil(y2*h)+margin)
        protected[top:bottom, left:right] = True

    # Preserve low-frequency RGB/shading and allow substantial *structural*
    # restoration on photographic contours. Clip only extreme hallucinations;
    # do NOT impose the +/-12 HAT detail limit that made the assist inert.
    detail = restored-base
    low_freq = cv2.GaussianBlur(detail, (0, 0), 6.0)
    detail = np.clip(detail-low_freq, -90, 90)
    safe = (~protected).astype(np.float32)
    out = np.rint(np.clip(base + detail * (safe*strength)[..., None],
                         0, 255)).astype(np.uint8)
    # Exact restoration of unselected graphic ink or face pixels.
    out[protected] = original[protected]
    return out


def blend_photo_only(original: np.ndarray, deblurred: np.ndarray,
                     strength: float = 1.0, protected_regions=()) -> np.ndarray:
    """Photo-only experiment: transfer NAFNet's actual restored RGB signal.

    The earlier sign-ink high-pass blend discarded much of NAFNet's useful
    low-frequency correction on genuine photographs (raw +4.63dB source PSNR
    vs protected +1.55dB on an astronaut motion-blur sample). This path is
    EXPLICITLY for photographs, not a poster containing text/logos. Selected
    face ROIs remain bitwise original ahead of V2 GFPGAN restoration.
    """
    if (original.shape != deblurred.shape or original.ndim != 3
            or original.shape[-1] != 3
            or original.dtype != np.uint8 or deblurred.dtype != np.uint8):
        raise ValueError("NAFNet photo-only requires matching uint8 RGB")
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("NAFNet photo-only strength must be finite 0..1")
    if strength == 0:
        return original.copy()
    blended = np.rint(
        original.astype(np.float32) * (1.0-strength)
        + deblurred.astype(np.float32) * strength
    ).astype(np.uint8)
    h, w = original.shape[:2]
    for rect in protected_regions or ():
        if len(rect) != 4 or not all(math.isfinite(float(v)) for v in rect):
            raise ValueError("Invalid photo-only face rectangle")
        x1, y1, x2, y2 = map(float, rect)
        if not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1:
            raise ValueError("NAFNet photo-only face selection must be normalized")
        margin = max(4, round(min((x2-x1)*w, (y2-y1)*h)*.15))
        l, t = max(0, math.floor(x1*w)-margin), max(0, math.floor(y1*h)-margin)
        r, b = min(w, math.ceil(x2*w)+margin), min(h, math.ceil(y2*h)+margin)
        blended[t:b, l:r] = original[t:b, l:r]
    return blended


class NAFNetGoProDeblurrer:
    """Bounded 1x NAFNet deblur. Shares source-tile orchestration with SwinIR."""

    def __init__(self, selected):
        checkpoint = nafnet_checkpoint_path()
        verify_nafnet_checkpoint(checkpoint)
        try:
            import torch
            import torch.nn.functional as functional
            from spandrel import ImageModelDescriptor, ModelLoader
        except ImportError as exc:
            raise RuntimeError("V2.1.1 NAFNet needs PyTorch + Spandrel") from exc
        if str(selected.backend).upper() == "DIRECTML":
            raise RuntimeError("NAFNet DirectML unverified; use CPU or CUDA")
        self.torch = torch
        self.functional = functional
        self.selected = selected
        self.device = torch.device(selected.device_id)
        descriptor = ModelLoader().load_from_file(str(checkpoint))
        if not isinstance(descriptor, ImageModelDescriptor):
            raise RuntimeError("NAFNet is not an image-model checkpoint")
        if (str(descriptor.architecture.id).lower() != "nafnet"
                or descriptor.scale != 1
                or descriptor.input_channels != 3
                or descriptor.output_channels != 3):
            raise RuntimeError("Expected 1x RGB NAFNet deblur architecture")
        self.model = descriptor.to(self.device).eval()
        self.upsampler = SimpleNamespace(tile_size=96, tile_pad=24)

    def denoise_tile(self, pixels, cancel_check=None):
        """1x deblur: method name matches existing optional preprocessor ABI."""
        if cancel_check and cancel_check():
            raise InterruptedError("Processing cancelled")
        if (pixels.ndim != 3 or pixels.shape[2] != 3
                or pixels.dtype != np.uint8):
            raise ValueError("NAFNet requires uint8 RGB")
        h, w = pixels.shape[:2]
        # NAFNet uses four encoder downsampling stages: 16× alignment.
        pad_bottom, pad_right = (-h) % 16, (-w) % 16
        tensor = self.torch.from_numpy(np.ascontiguousarray(pixels))
        tensor = tensor.permute(2, 0, 1).unsqueeze(0)
        tensor = tensor.to(device=self.device, dtype=self.torch.float32) / 255
        if pad_bottom or pad_right:
            mode = ("reflect" if pad_bottom < h and pad_right < w
                    else "replicate")
            tensor = self.functional.pad(
                tensor, (0, pad_right, 0, pad_bottom), mode=mode
            )
        with self.torch.inference_mode():
            output = self.model(tensor)
        if tuple(output.shape) != (1, 3, h+pad_bottom, w+pad_right):
            raise RuntimeError("NAFNet 1x output dimensions are incorrect")
        if not bool(self.torch.isfinite(output).all()):
            raise RuntimeError("NAFNet output contains NaN or Inf")
        out = np.rint(
            np.clip(output[0, :, :h, :w].permute(1, 2, 0)
                    .float().cpu().numpy(), 0, 1) * 255
        ).astype(np.uint8)
        if cancel_check and cancel_check():
            raise InterruptedError("Processing cancelled")
        return out
