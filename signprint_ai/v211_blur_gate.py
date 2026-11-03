"""Conservative photo-only blur gate for the experimental NAFNet + V2 path.

This is intentionally NOT a universal blur classifier, and never enables
AI restoration automatically. It decides only whether an ALREADY explicitly
selected, research-only PHOTO NAFNet processor may run. V2 remains the safe
fallback on sharp, uncertain, graphic, transparent or unconfirmed-face input.
Models and V1/V2 stable code are not modified here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class PhotoBlurDecision:
    allow: bool
    reason: str
    # Scalar metrics for diagnostics; these do not certify reconstruction.
    laplacian_std: float = 0.0
    edge_mean: float = 0.0
    highpass_fraction: float = 0.0
    edge_fraction: float = 0.0

    def as_dict(self):
        return {
            "allow": self.allow,
            "reason": self.reason,
            "laplacian_std": round(self.laplacian_std, 4),
            "edge_mean": round(self.edge_mean, 4),
            "highpass_fraction": round(self.highpass_fraction, 5),
            "edge_fraction": round(self.edge_fraction, 5),
            "automatic_quality_certified": False,
        }


def assess_explicit_photo_blur(image: np.ndarray) -> PhotoBlurDecision:
    """Fail closed when no strong evidence of *motion-blurred* photo detail.

    Sharp portrait/café images tested in V2.1.1 regressed with NAFNet despite
    improvements on blurred astronaut photos. A single Laplacian threshold
    would flag smooth but sharp images, so use several independent signals.
    The gate intentionally allows false negatives rather than exposing users
    to an irreversible face/lettering quality regression.
    """
    if (not isinstance(image, np.ndarray) or image.ndim != 3
            or image.shape[2] != 3 or image.dtype != np.uint8):
        raise ValueError("Blur preflight expects uint8 RGB pixels")
    h, w = image.shape[:2]
    if h < 64 or w < 64:
        return PhotoBlurDecision(False, "small_or_unreliable_photo_crop")
    # Work only on a bounded preview to avoid image-master RAM allocations.
    if max(w, h) > 512:
        ratio = 512.0 / max(w, h)
        image = cv2.resize(image, (max(1, round(w*ratio)),
                                    max(1, round(h*ratio))),
                           interpolation=cv2.INTER_AREA)
    grey = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
    if not np.isfinite(grey).all():
        return PhotoBlurDecision(False, "invalid_pixels")
    contrast = float(grey.std())
    if contrast < 22.0:
        return PhotoBlurDecision(False, "low_information_or_flat_graphic")
    lap = cv2.Laplacian(grey, cv2.CV_32F, ksize=3)
    gx = cv2.Sobel(grey, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(grey, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    edge_mean = float(gradient.mean())
    edge_fraction = float(np.mean(gradient > 160))
    # Large, coherent flat high-saturation patches are usually sign/logo
    # ink rather than photographic material. Do not run a photo-trained
    # deblurrer across a poster, even when the raster itself is blurry.
    rgb_int = image.astype(np.int16)
    high_chroma = (rgb_int.max(axis=2) - rgb_int.min(axis=2)) > 105
    local_span = (
        cv2.dilate(image, np.ones((3, 3), np.uint8)).astype(np.int16)
        - cv2.erode(image, np.ones((3, 3), np.uint8)).astype(np.int16)
    ).max(axis=2)
    flat_vivid_ink = float(np.mean(high_chroma & (local_span <= 25)))
    if flat_vivid_ink > .42:
        return PhotoBlurDecision(False, "mostly_flat_saturated_graphic")
    highpass = grey - cv2.GaussianBlur(grey, (0, 0), 1.0)
    highpass_fraction = float(highpass.std() / max(contrast, 1.0))
    lap_std = float(lap.std())
    ratio = lap_std / max(edge_mean, 1.0)
    values = (lap_std, edge_mean, edge_fraction, highpass_fraction, ratio)
    if not all(math.isfinite(x) for x in values):
        return PhotoBlurDecision(False, "invalid_blur_metric")
    # Both a weak fine-detail spectrum AND remaining recognizable edges are
    # required. Mildly smooth, already-sharp photos should bypass NAFNet.
    if (lap_std < 75.0 and ratio < .95 and highpass_fraction < .12
            and edge_fraction > .008 and edge_mean > 12.0):
        return PhotoBlurDecision(True, "motion_blur_evidence", lap_std,
                                 edge_mean, highpass_fraction, edge_fraction)
    return PhotoBlurDecision(False, "not_confidently_motion_blurred",
                             lap_std, edge_mean, highpass_fraction,
                             edge_fraction)


def select_photo_restoration(settings, source_path, *, use_ai: bool,
                             model_scale: int):
    """Return (possibly V2-only settings, audit record) *before* inference.

    Never allow NAFNet photo-only on RGBA print cutouts, uncertain motion blur,
    or a requested GFPGAN face restoration without confirmed source face
    regions. Metadata explicitly records the V2 fallback; never silently
    pretend NAFNet ran.
    """
    if getattr(settings, "v211_photo_model", "") != "v2_nafnet_photo_only":
        return settings, None
    from dataclasses import replace
    from .large_image import source_declares_alpha, thumbnail

    def bypass(reason, metrics=None):
        audit = {
            "requested_model": "v2_nafnet_photo_only",
            "actual_model": "real_esrgan",
            "reason": reason,
            "automatic_quality_certified": False,
        }
        if metrics is not None:
            audit["blur_metrics"] = metrics.as_dict()
        return replace(settings, v211_photo_model="real_esrgan"), audit

    if not use_ai or model_scale <= 1:
        return bypass("ai_is_disabled")
    if source_declares_alpha(source_path):
        # V2 can process RGBA safely; experimental photo-only denoising has
        # not been proven safe on transparent logo/cutout boundaries.
        return bypass("transparent_png_or_tiff_keep_v2")
    if (getattr(settings, "face_protection", False)
            and str(getattr(settings, "face_mode", "")).lower()
            in ("recover", "studio ai")
            and getattr(settings, "face_regions", None) is None):
        return bypass("confirm_detected_faces_before_experimental_photo_deblur")
    image = np.asarray(thumbnail(source_path, (512, 512)).convert("RGB"))
    decision = assess_explicit_photo_blur(image)
    if not decision.allow:
        return bypass("sharp_or_uncertain_input_keep_v2", decision)
    return settings, {
        "requested_model": "v2_nafnet_photo_only",
        "actual_model": "v2_nafnet_photo_only",
        "reason": decision.reason,
        "blur_metrics": decision.as_dict(),
        "automatic_quality_certified": False,
    }
