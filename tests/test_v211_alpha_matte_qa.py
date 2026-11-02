"""Regression tests for optional alpha-matte A/B diagnostic."""
import numpy as np
import pytest
from PIL import Image
from tools.v211_alpha_matte_qa import compare_alpha_mattes


def pair(tmp_path, a, b):
    p, q = tmp_path / "v2.png", tmp_path / "candidate.png"
    Image.fromarray(a, "RGBA").save(p)
    Image.fromarray(b, "RGBA").save(q)
    return p, q


def test_alpha_change_is_reported_not_rejected(tmp_path):
    a = np.zeros((16, 16, 4), dtype=np.uint8)
    a[4:12, 4:12] = (200, 30, 40, 128)
    b = a.copy()
    b[4:12, 4:12, 3] = 180
    report = compare_alpha_mattes(*pair(tmp_path, a, b))
    assert report["alpha_changed_pixels"] == 64
    assert report["review_required"]
    assert not report["quality_improvement_certified"]
    assert len(report["mattes"]) == 4


def test_hidden_rgb_is_invisible_on_every_matte(tmp_path):
    a = np.zeros((16, 16, 4), dtype=np.uint8)
    a[4:12, 4:12] = (200, 30, 40, 255)
    b = a.copy()
    b[:4, :, :3] = 255
    report = compare_alpha_mattes(*pair(tmp_path, a, b))
    assert report["alpha_changed_pixels"] == 0
    assert all(v["mean_visible_channel_delta"] == 0 for v in report["mattes"].values())
    assert not report["review_required"]


def test_translucent_colour_fringe_detected(tmp_path):
    a = np.zeros((16, 16, 4), dtype=np.uint8)
    a[4:12, 4:12] = (200, 30, 40, 128)
    b = a.copy()
    b[4:12, 4:12, :3] = (20, 20, 220)
    report = compare_alpha_mattes(*pair(tmp_path, a, b))
    assert report["review_required"]
    assert all(v["edge_changed_gt_12_pct"] > 1 for v in report["mattes"].values())


def test_reject_missing_alpha(tmp_path):
    p = tmp_path / "a.png"
    q = tmp_path / "b.png"
    Image.new("RGB", (8, 8)).save(p)
    Image.new("RGBA", (8, 8)).save(q)
    with pytest.raises(ValueError, match="explicit alpha"):
        compare_alpha_mattes(p, q)
