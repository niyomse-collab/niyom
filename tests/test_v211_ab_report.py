"""Regression tests for objective, offline V2 / V2.1.1 visual comparisons."""
import json

import numpy as np
import pytest
from PIL import Image

from tools.v211_ab_report import (
    _check_qa_size, compare_images, main, render_comparison,
)


def _write_pair(tmp_path):
    v2, enhanced = tmp_path / "v2.png", tmp_path / "super.png"
    base = np.zeros((40, 60, 3), dtype=np.uint8)
    base[:, :30] = (240, 20, 40)
    base[:, 30:] = (20, 80, 230)
    improved = base.copy()
    improved[:, 29:31] = np.clip(
        improved[:, 29:31].astype("int16") + 7, 0, 255
    ).astype(np.uint8)
    Image.fromarray(base).save(v2, dpi=(300, 300))
    Image.fromarray(improved).save(enhanced, dpi=(300, 300))
    return v2, enhanced


def test_ab_diagnostic_reports_changes_without_claiming_improvement(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    result = compare_images(v2, enhanced, face_regions=((0, 0, 0.3, 0.5),))
    assert result["same_pixels"] and result["same_alpha"] and result["same_icc"]
    assert result["overall"]["changed_gt_3_pct"] > 0
    assert result["existing_v2_edges"]["pixel_count"] > 0
    assert result["flat_ink_fills"]["pixel_count"] > 0
    assert result["selected_face_regions"]["pixel_count"] == 360
    assert result["quality_improvement_certified"] is False
    assert result["print_certified"] is False


def test_comparison_artifact_is_side_by_side_same_pixel_scale(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    comparison = tmp_path / "side-by-side.png"
    render_comparison(v2, enhanced, comparison)
    with Image.open(comparison) as result:
        assert result.size == (60 * 2 + 24, 40 + 35)


def test_local_cli_writes_noncertifying_evidence(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    out = tmp_path / "private-qa"
    main(["--v2", str(v2), "--super", str(enhanced), "--out", str(out)])
    data = json.loads((out / "quality_deltas.json").read_text(encoding="utf-8"))
    assert data["quality_improvement_certified"] is False
    assert (out / "v2_vs_super_ai.png").is_file()


def test_reject_mismatched_dimensions(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    Image.new("RGB", (59, 40)).save(enhanced)
    with pytest.raises(ValueError, match="different output pixel dimensions"):
        compare_images(v2, enhanced)


def test_reject_alpha_mismatch_even_if_rgb_matches(tmp_path):
    v2, enhanced = tmp_path / "v2.png", tmp_path / "super.png"
    alpha = np.zeros((12, 16, 4), dtype=np.uint8)
    alpha[:, :, :3] = (50, 90, 130)
    alpha[2:10, 2:10, 3] = 255
    Image.fromarray(alpha, "RGBA").save(v2)
    alpha[2:10, 2:10, 3] = 240
    Image.fromarray(alpha, "RGBA").save(enhanced)
    with pytest.raises(ValueError, match="alpha planes differ"):
        compare_images(v2, enhanced)


def test_reject_different_dpi_and_icc(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    Image.new("RGB", (60, 40)).save(enhanced, dpi=(72, 72))
    with pytest.raises(ValueError, match="DPI"):
        compare_images(v2, enhanced)
    Image.new("RGB", (60, 40)).save(enhanced, dpi=(300, 300),
                                     icc_profile=b"unrelated profile")
    with pytest.raises(ValueError, match="ICC"):
        compare_images(v2, enhanced)


def test_reject_nonfinite_face_selection(tmp_path):
    v2, enhanced = _write_pair(tmp_path)
    with pytest.raises(ValueError, match="finite normalized"):
        compare_images(v2, enhanced, face_regions=((0, 0, float("nan"), 1),))


def test_bounded_qa_does_not_allocate_a_whole_vinyl_master():
    _check_qa_size((500, 500))
    with pytest.raises(ValueError, match="16 megapixels"):
        _check_qa_size((20000, 12000))
