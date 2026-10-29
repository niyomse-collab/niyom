"""V2.1-only conservative quality check before pasting a generated face.

Not a biometric identity check. Rejects catastrophic GAN outputs (flat crops,
severe detail loss, major colour or content drift), preserving the original
upscaled face pixels instead of painting an implausible replacement.
"""
from __future__ import annotations

import cv2
import numpy as np


def check_face_restoration(original_bgr, candidate_bgr):
    """Return (accepted, reason); never mutate either image."""
    if (
        not isinstance(original_bgr, np.ndarray)
        or not isinstance(candidate_bgr, np.ndarray)
        or original_bgr.dtype != np.uint8
        or candidate_bgr.dtype != np.uint8
        or original_bgr.shape != candidate_bgr.shape
        or original_bgr.ndim != 3
        or original_bgr.shape[2] != 3
        or min(original_bgr.shape[:2]) < 32
    ):
        return False, "invalid_face_crop"

    if float(candidate_bgr.std(axis=(0, 1)).mean()) < 2.0:
        return False, "collapsed_face_content"

    original = original_bgr.astype(np.float32)
    candidate = candidate_bgr.astype(np.float32)
    if float(np.abs(original - candidate).mean()) > 65.0:
        return False, "excessive_face_change"

    old_gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
    new_gray = cv2.cvtColor(candidate_bgr, cv2.COLOR_BGR2GRAY)
    old_detail = cv2.Laplacian(old_gray, cv2.CV_32F, ksize=3)
    new_detail = cv2.Laplacian(new_gray, cv2.CV_32F, ksize=3)
    old_energy = float(np.mean(old_detail * old_detail))
    new_energy = float(np.mean(new_detail * new_detail))
    if old_energy > 35.0 and new_energy < old_energy * 0.20:
        return False, "face_detail_collapsed"

    old_low = cv2.GaussianBlur(original_bgr, (0, 0), 5.0).astype(np.float32)
    new_low = cv2.GaussianBlur(candidate_bgr, (0, 0), 5.0).astype(np.float32)
    channel_shift = np.mean(new_low - old_low, axis=(0, 1))
    if np.max(np.abs(channel_shift)) > 35.0:
        return False, "face_colour_drift"

    return True, "accepted"
