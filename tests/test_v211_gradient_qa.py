"""Synthetic gradient diagnostic regression, not neural/print acceptance."""
import numpy as np
import pytest
from PIL import Image
from tools.v211_gradient_qa import compare_gradient_roi


def save_pair(tmp_path, a, b):
    p, q = tmp_path / "v2.png", tmp_path / "candidate.png"
    Image.fromarray(a, "RGBA").save(p)
    Image.fromarray(b, "RGBA").save(q)
    return p, q


def test_new_gradient_banding_is_flagged(tmp_path):
    x = np.linspace(30, 200, 64).astype(np.uint8)
    a = np.empty((12, 64, 4), dtype=np.uint8)
    a[..., :3] = x[None, :, None]
    a[..., 3] = 255
    b = a.copy()
    b[..., :3] = (b[..., :3] // 32) * 32
    report = compare_gradient_roi(*save_pair(tmp_path, a, b), (0, 0, 64, 12))
    assert report["new_large_jumps_review_required"]
    assert report["candidate"]["adjacent_jump_gt_16_pct"] > report["v2"]["adjacent_jump_gt_16_pct"]
    assert not report["quality_improvement_certified"]


def test_unchanged_gradient_not_flagged(tmp_path):
    a = np.full((12, 64, 4), (80, 120, 160, 255), dtype=np.uint8)
    report = compare_gradient_roi(*save_pair(tmp_path, a, a), (0, 0, 64, 12))
    assert not report["new_large_jumps_review_required"]


def test_transparency_rejected(tmp_path):
    a = np.full((12, 64, 4), (80, 120, 160, 255), dtype=np.uint8)
    b = a.copy()
    b[3, 3, 3] = 128
    with pytest.raises(ValueError, match="fully opaque"):
        compare_gradient_roi(*save_pair(tmp_path, a, b), (0, 0, 64, 12))


def test_bad_roi_and_axis_rejected(tmp_path):
    a = np.full((12, 64, 4), (80, 120, 160, 255), dtype=np.uint8)
    paths = save_pair(tmp_path, a, a)
    with pytest.raises(ValueError, match="outside"):
        compare_gradient_roi(*paths, (0, 0, 65, 12))
    with pytest.raises(ValueError, match="axis"):
        compare_gradient_roi(*paths, (0, 0, 64, 12), axis="diagonal")
