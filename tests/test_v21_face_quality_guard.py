"""V2.1 safety gate for GFPGAN face crops, synthetic data only.

These are failure-prevention tests, not biometric identity verification.
"""
import cv2
import numpy as np

from signprint_ai.face_module.face_quality_guard import check_face_restoration
from signprint_ai.face_module.face_protection import FaceProtectionModule


def synthetic_face():
    rng = np.random.default_rng(222)
    y, x = np.ogrid[:128, :128]
    pix = np.full((128, 128, 3), [112, 156, 191], dtype=np.float32)
    pix += rng.normal(0, 5, pix.shape)
    for cx in (44, 84):
        eye = (x-cx)**2 + (y-50)**2 < 9**2
        pix[eye] = [29, 39, 57]
    mouth = ((x-64)/23)**2 + ((y-94)/5)**2 < 1
    pix[mouth] = [55, 54, 128]
    return np.clip(pix, 0, 255).astype(np.uint8)


def test_accepts_mild_restoration():
    original = synthetic_face()
    edited = cv2.bilateralFilter(original, 5, 13, 2)
    assert check_face_restoration(original, edited) == (True, "accepted")


def test_rejects_wrong_shape_or_type():
    image = synthetic_face()
    assert check_face_restoration(image, image[:64])[1] == "invalid_face_crop"
    assert check_face_restoration(image, image.astype(np.float32))[1] == "invalid_face_crop"


def test_rejects_flat_unrecognizable_face():
    image = synthetic_face()
    assert check_face_restoration(image, np.full_like(image, 128))[1] == "collapsed_face_content"


def test_rejects_face_that_loses_eyes_and_mouth():
    image = synthetic_face()
    ruined = cv2.GaussianBlur(image, (0, 0), 22)
    assert check_face_restoration(image, ruined)[1] == "face_detail_collapsed"


def test_rejects_severe_colour_shift():
    image = synthetic_face()
    changed = np.clip(image.astype(np.int16) + [43, 0, 0], 0, 255).astype(np.uint8)
    assert check_face_restoration(image, changed)[1] == "face_colour_drift"


def test_guard_never_mutates_original_or_candidate():
    image = synthetic_face()
    edited = cv2.bilateralFilter(image, 5, 13, 2)
    old, new = image.copy(), edited.copy()
    check_face_restoration(image, edited)
    np.testing.assert_array_equal(image, old)
    np.testing.assert_array_equal(edited, new)


def test_recover_strength_capped_to_avoid_gan_dominating_face():
    assert FaceProtectionModule._blend_alpha("recover", 100) <= 0.5
    assert FaceProtectionModule._blend_alpha("recover", 35) == 0.35
    assert FaceProtectionModule._blend_alpha("protect", 100) <= 0.45
