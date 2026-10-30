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


def test_recover_preserves_proven_v2_gfpgan_strength():
    # V2's recover blend is the user-approved portrait baseline.
    assert FaceProtectionModule._blend_alpha("recover", 100) == 0.75
    assert FaceProtectionModule._blend_alpha("recover", 65) == 0.65
    assert FaceProtectionModule._blend_alpha("recover", 35) == 0.35
    assert FaceProtectionModule._blend_alpha("protect", 100) <= 0.45


def test_v21_face_recover_uses_v2_gfpgan_without_quality_veto():
    # Regression: a candidate face must not be replaced with the blurred
    # source merely because a heuristic quality guard vetoed GFPGAN.
    import inspect

    apply_source = inspect.getsource(FaceProtectionModule.apply)
    assert "network(face_tensor, return_rgb=False, weight=0.5)" in apply_source
    assert "helper.add_restored_face(restored_face)" in apply_source
    assert "check_face_restoration(" not in apply_source


def test_rejects_local_eye_erasure_even_when_other_face_detail_survives():
    original = synthetic_face()
    damaged = original.copy()
    # Removing one eye leaves global detail energy high; a whole-face
    # average alone can miss this catastrophic localized regression.
    damaged[41:59, 35:53] = [112, 156, 191]
    assert check_face_restoration(original, damaged)[1] == "local_face_detail_collapsed"


def test_rejects_local_mouth_erasure_even_when_eyes_remain():
    original = synthetic_face()
    damaged = original.copy()
    damaged[88:101, 41:87] = [112, 156, 191]
    assert check_face_restoration(original, damaged)[1] == "local_face_detail_collapsed"


def test_v21_face_audit_warns_without_vetoing_recover_output():
    from signprint_ai.face_module.face_protection import _audit_restored_face
    original = synthetic_face()
    ruined = cv2.GaussianBlur(original, (0, 0), 22)
    before = ruined.copy()
    audit = _audit_restored_face(original, ruined, 1)
    assert audit["index"] == 1
    assert audit["model"] == "GFPGANv1.4"
    assert audit["applied"] is True
    assert audit["heuristic_pass"] is False
    assert audit["reason"] in {"face_detail_collapsed", "local_face_detail_collapsed"}
    assert audit["retry"] == "adjust_face_strength_and_reprocess"
    np.testing.assert_array_equal(ruined, before)


def test_v21_face_audit_serializes_warning_and_accepted_pass():
    from signprint_ai.face_module.face_protection import FaceProtectionResult, _audit_restored_face
    original = synthetic_face()
    accepted = _audit_restored_face(original, original.copy(), 2)
    assert accepted["heuristic_pass"] is True
    assert accepted["retry"] is None
    warning = _audit_restored_face(original, np.full_like(original, 128), 3)
    result = FaceProtectionResult(
        enabled=True, applied=True, face_count=2, mode="recover",
        strength=75, face_audit=(accepted, warning),
    )
    exported = result.as_dict()
    assert exported["applied"] is True
    assert len(exported["face_audit"]) == 2
    assert exported["face_audit"][1]["reason"] == "collapsed_face_content"
    exported["face_audit"][0]["reason"] = "modified"
    assert result.face_audit[0]["reason"] == "accepted"
