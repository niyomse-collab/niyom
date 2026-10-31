"""V2.1.1 experimental *pre-restoration* of photographic pixels with SwinIR.

This is an independent upstream colour-noise-15 SwinIR 1x neural model, not
the HAT post-sharpening blend. It runs BEFORE V2 Real-ESRGAN; the normal
V2 GFPGAN face recovery still runs afterward. Only the experimental branch
loads the optional, verified model, never V1/V2 stable.

The model is NOT automatically downloaded or shipped. Real CPU inference,
photographic quality, GPU, Windows packaging and commercial weight terms
must pass QA before release. The default V2 path is unchanged.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageOps

SWINIR_FILE = "005_colorDN_DFWB_s128w8_SwinIR-M_noise15.pth"
# Captured from the official upstream v0.0 release in the separate
# provenance job #41154552984; never trust an unverified local replacement.
SWINIR_SHA256 = "917cd972f7ba80786871add249ad43e4477ce2db59b4ad63e2fa446f7221d013"
SWINIR_BYTES = 122905743
SWINIR_RELEASE_URL = (
    "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/" + SWINIR_FILE
)


def swinir_checkpoint_path() -> Path:
    from .face_module.face_protection import resource_root
    return resource_root() / "models" / "experimental" / SWINIR_FILE


def verify_swinir_checkpoint(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            "V2.1.1 SwinIR: ยังไม่ติดตั้งโมเดลลด Noise สีที่ตรวจสอบแล้ว"
        )
    if path.stat().st_size != SWINIR_BYTES:
        raise RuntimeError("V2.1.1 SwinIR: ขนาด checkpoint ไม่ตรงกับรุ่นที่ตรวจสอบ")
    with path.open("rb") as src:
        actual = hashlib.file_digest(src, "sha256").hexdigest()
    if actual != SWINIR_SHA256:
        raise RuntimeError("V2.1.1 SwinIR: SHA256 ไม่ตรงกับ checkpoint ทางการ")


def _pad_shape(height: int, width: int, window: int = 8):
    if height < 1 or width < 1:
        raise ValueError("SwinIR requires positive source dimensions")
    bottom, right = (-height) % window, (-width) % window
    return bottom, right, ("reflect" if bottom < height and right < width
                           else "replicate")


def blend_pre_restoration(original: np.ndarray, restored: np.ndarray,
                          strength: float = .70, protected_regions=()) -> np.ndarray:
    """Accept denoising on textured interiors; never rewrite lettering edges.

    This is a conservative research mask. A larger difference is NOT proof of
    an improvement; reference-image PSNR/SSIM and visual checks still govern.
    """
    if (original.shape != restored.shape or original.ndim != 3
            or original.shape[2] != 3 or original.dtype != np.uint8
            or restored.dtype != np.uint8):
        raise ValueError("SwinIR pre-restoration expects matching uint8 RGB")
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("SwinIR strength must be finite and in [0, 1]")
    if strength == 0:
        return original.copy()
    f = original.astype(np.float32)
    h, w = original.shape[:2]
    # Build the *structural* edge mask from a softly filtered copy.
    # Raw Sobel over Gaussian noise sigma=15 marks almost every pixel as an
    # "edge" and disables the very denoising this stage is meant to perform.
    # Blur ONLY for edge detection, never as the restored image itself.
    structure = cv2.GaussianBlur(f, (0, 0), 1.15)
    gx = cv2.Sobel(structure, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(structure, cv2.CV_32F, 0, 1, ksize=3)
    edges = np.max(np.sqrt(gx * gx + gy * gy), axis=2) > 60.0
    # Dilating the mask protects thin Thai/English glyph strokes and outlines
    # from blur/shape changes even near their boundaries.
    edges = cv2.dilate(edges.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    grey = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY).astype(np.float32)
    local_mean = cv2.boxFilter(grey, cv2.CV_32F, (5, 5))
    local_sq = cv2.boxFilter(grey * grey, cv2.CV_32F, (5, 5))
    local_sd = np.sqrt(np.maximum(local_sq - local_mean * local_mean, 0))
    # Do not modify completely flat ink or very structured/sharp regions.
    candidates = (~edges) & (local_sd >= 2.0) & (local_sd <= 40.0)
    for rect in protected_regions or ():
        if len(rect) != 4 or not all(math.isfinite(float(v)) for v in rect):
            raise ValueError("Invalid normalized face region for SwinIR")
        x1, y1, x2, y2 = map(float, rect)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("SwinIR face regions must be normalized to [0, 1]")
        margin = max(4, round(min((x2 - x1) * w, (y2 - y1) * h) * .15))
        l, t = max(0, math.floor(x1 * w) - margin), max(0, math.floor(y1 * h) - margin)
        r, b = min(w, math.ceil(x2 * w) + margin), min(h, math.ceil(y2 * h) + margin)
        candidates[t:b, l:r] = False
    # Cap changes per channel so SwinIR never changes global colour balance.
    difference = np.clip(restored.astype(np.int16) - original.astype(np.int16), -24, 24)
    weight = (candidates.astype(np.float32) * strength)[..., None]
    return np.rint(np.clip(f + difference * weight, 0, 255)).astype(np.uint8)


class SwinIRColorDenoiser:
    """Real SwinIR 1x colour denoising with bounded attention-window tiles."""

    def __init__(self, selected):
        checkpoint = swinir_checkpoint_path()
        verify_swinir_checkpoint(checkpoint)
        try:
            import torch
            from spandrel import ImageModelDescriptor, ModelLoader
        except ImportError as exc:
            raise RuntimeError("V2.1.1 SwinIR needs PyTorch and spandrel") from exc
        if str(selected.backend).upper() == "DIRECTML":
            raise RuntimeError("SwinIR DirectML is not verified; choose CPU/CUDA")
        self.torch = torch
        self.selected = selected
        self.device = torch.device(selected.device_id)
        descriptor = ModelLoader().load_from_file(str(checkpoint))
        if not isinstance(descriptor, ImageModelDescriptor):
            raise RuntimeError("SwinIR checkpoint is not an image model")
        if (descriptor.scale != 1 or descriptor.input_channels != 3
                or descriptor.output_channels != 3):
            raise RuntimeError("Expected RGB 1x SwinIR colour denoising model")
        if str(descriptor.architecture.id).upper() != "SWINIR":
            raise RuntimeError("Expected SwinIR architecture")
        self.model = descriptor.to(self.device).eval()
        # Small tiles deliberately limit intermediate attention memory.
        self.upsampler = SimpleNamespace(tile_size=64, tile_pad=24)

    def denoise_tile(self, pixels, cancel_check=None):
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        if (pixels.ndim != 3 or pixels.shape[2] != 3
                or pixels.dtype != np.uint8):
            raise ValueError("SwinIR needs uint8 RGB")
        h, w = pixels.shape[:2]
        bottom, right, mode = _pad_shape(h, w)
        import torch.nn.functional as functional
        tensor = self.torch.from_numpy(np.ascontiguousarray(pixels)).permute(2, 0, 1)
        tensor = tensor.unsqueeze(0).to(self.device, dtype=self.torch.float32) / 255.
        if bottom or right:
            tensor = functional.pad(tensor, (0, right, 0, bottom), mode=mode)
        with self.torch.inference_mode():
            out = self.model(tensor)
        if tuple(out.shape) != (1, 3, h + bottom, w + right):
            raise RuntimeError("SwinIR 1x output size does not match source")
        if not bool(self.torch.isfinite(out).all()):
            raise RuntimeError("SwinIR returned NaN/Inf")
        out = out[:, :, :h, :w]
        result = np.rint(np.clip(
            out.squeeze(0).permute(1, 2, 0).float().cpu().numpy(), 0, 1
        ) * 255).astype(np.uint8)
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        return result


class PreRestoreV2Engine:
    """Perform optional 1x pre-restoration once; upscale with ORIGINAL V2."""

    def __init__(self, v2_engine, denoiser, strength=.70, protected_regions=(),
                 blend_callback=None):
        self.v2 = v2_engine
        self.denoiser = denoiser
        self.strength = strength
        self.protected_regions = protected_regions
        self.blend_callback = blend_callback or blend_pre_restoration
        self.upsampler = SimpleNamespace(
            tile_size=min(v2_engine.upsampler.tile_size or 256,
                          denoiser.upsampler.tile_size or 64),
            tile_pad=max(v2_engine.upsampler.tile_pad, denoiser.upsampler.tile_pad),
        )

    def device_name(self):
        return self.v2.device_name()

    def next_pass_engine(self):
        """No second denoise: 8x means pre-restore -> V2 4x -> V2 2x."""
        return self.v2

    def enhance_graphic_tile(self, pixels, scale, cancel, protected_regions=()):
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")
        # The large-image tile adapter expresses a partially overlapping
        # face ROI in tile coordinates; clipping prevents out-of-range masks
        # and keeps the face excluded even on boundary tiles.
        cropped_regions = []
        for x1, y1, x2, y2 in protected_regions or ():
            if not all(math.isfinite(float(v)) for v in (x1, y1, x2, y2)):
                raise ValueError("Invalid face region in source tile")
            a, b = max(0., float(x1)), max(0., float(y1))
            c, d = min(1., float(x2)), min(1., float(y2))
            if c > a and d > b:
                cropped_regions.append((a, b, c, d))
        denoised = self.denoiser.denoise_tile(pixels, cancel)
        restored = self.blend_callback(
            pixels, denoised, self.strength, tuple(cropped_regions)
        )
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")
        if hasattr(self.v2, "enhance_graphic_tile"):
            return self.v2.enhance_graphic_tile(restored, scale, cancel, protected_regions)
        return self.v2.enhance_tile(restored, scale, cancel)

    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        return self.enhance_graphic_tile(
            pixels, scale, cancel_check, self.protected_regions
        )

    def enhance(self, src, dst, scale=4, progress_callback=None, cancel_check=None):
        with Image.open(src) as raw:
            pixels = np.asarray(ImageOps.exif_transpose(raw).convert("RGB")).copy()
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        # Input fits the small-image pipeline; print masters take tile path.
        step = self.upsampler.tile_size
        pad = self.upsampler.tile_pad
        h, w = pixels.shape[:2]
        restored = np.empty_like(pixels)
        for y in range(0, h, step):
            for x in range(0, w, step):
                if cancel_check and cancel_check():
                    raise InterruptedError("Processing stopped by user")
                y2, x2 = min(h, y + step), min(w, x + step)
                t, l = max(0, y - pad), max(0, x - pad)
                b, r = min(h, y2 + pad), min(w, x2 + pad)
                crop = pixels[t:b, l:r]
                # Regions are normalized to whole-image coordinates; map into
                # this padded source tile before blending.
                tile_regions = tuple(
                    (max(0., (x1*w-l)/(r-l)), max(0., (y1*h-t)/(b-t)),
                     min(1., (x2*w-l)/(r-l)), min(1., (y2*h-t)/(b-t)))
                    for x1, y1, x2, y2 in self.protected_regions or ()
                    if x2*w > l and x1*w < r and y2*h > t and y1*h < b
                )
                clean = self.denoiser.denoise_tile(crop, cancel_check)
                blended = self.blend_callback(
                    crop, clean, self.strength, tile_regions
                )
                restored[y:y2, x:x2] = blended[y-t:y2-t, x-l:x2-l]
        if cancel_check and cancel_check():
            raise InterruptedError("Processing stopped by user")
        with TemporaryDirectory(prefix="niyomsil_v211_swinir_") as folder:
            preprocessed = Path(folder) / "preprocessed.png"
            Image.fromarray(restored, "RGB").save(preprocessed)
            return self.v2.enhance(
                preprocessed, dst, scale=scale,
                progress_callback=progress_callback, cancel_check=cancel_check
            )
