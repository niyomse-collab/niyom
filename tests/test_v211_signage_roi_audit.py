"""Regression tests for private ROI source samples and V2/V2.1.1 comparisons."""
import json

import numpy as np
import pytest
from PIL import Image

from tools.v211_signage_roi_audit import load_regions, run_audit


def _regions(path):
    path.write_text(json.dumps({"regions": [
        {"id": "headline", "kind": "styled_fx_text", "box": [.1, 0, .9, .5]},
        {"id": "ornament", "kind": "transparent_edge", "box": [0, .5, 1, 1]},
    ]}))
    return path


def test_source_only_is_not_a_model_ab(tmp_path):
    src = tmp_path / "source.png"
    Image.new("RGBA", (72, 48), (250, 170, 10, 210)).save(src)
    result = run_audit(src, _regions(tmp_path / "rois.json"), tmp_path / "qa")
    assert result["ab_comparison_available"] is False
    assert result["quality_improvement_certified"] is False
    assert len(result["regions"]) == 2
    assert (tmp_path / "qa/headline_black.png").is_file()
    assert (tmp_path / "qa/ornament_red.png").is_file()
    assert (tmp_path / "qa/SIGNAGE_ROI_REPORT.json").is_file()


def test_matched_pair_reports_delta_without_certification(tmp_path):
    src, baseline, experimental = (tmp_path / name for name in
                                   ("src.png", "v2.png", "super.png"))
    Image.new("RGBA", (28, 20), (200, 100, 30, 255)).save(src)
    pixels = np.empty((40, 56, 4), dtype=np.uint8)
    pixels[:, :, :] = (200, 100, 30, 255)
    pixels[:, 28:, :3] = (20, 40, 200)
    Image.fromarray(pixels, "RGBA").save(baseline, dpi=(300, 300))
    pixels[0:9, 20:30, :3] = (203, 103, 33)
    Image.fromarray(pixels, "RGBA").save(experimental, dpi=(300, 300))
    result = run_audit(src, _regions(tmp_path / "rois.json"),
                       tmp_path / "qa", v2=baseline, super_path=experimental)
    assert result["ab_comparison_available"] is True
    assert result["regions"][0]["v2_to_v211_change"]["changed_gt3_pct"] > 0
    assert result["regions"][0]["v2_to_v211_change"]["mean_abs_rgb_change"] > 0
    assert result["quality_improvement_certified"] is False
    with Image.open(tmp_path / "qa/headline_gray.png") as image:
        assert image.width > 3 * 20


@pytest.mark.parametrize("bad", [
    {"regions": []},
    {"regions": [{"id": "../danger", "kind": "face", "box": [0, 0, 1, 1]}]},
    {"regions": [{"id": "x", "kind": "styled_fx_text", "box": [0, 0, float("nan"), 1]}]},
    {"regions": [{"id": "x", "kind": "fake", "box": [0, 0, 1, 1]}]},
    {"regions": [{"id": "x", "kind": "face", "box": [0, 0, 1, 1]},
                 {"id": "x", "kind": "face", "box": [0, 0, 1, 1]}]},
])
def test_malformed_regions_rejected(tmp_path, bad):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_regions(path)


def test_one_sided_comparison_fails_without_writing(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (30, 20)).save(src)
    dest = tmp_path / "qa"
    with pytest.raises(ValueError, match="both --v2 and --super"):
        run_audit(src, _regions(tmp_path / "regions.json"), dest, v2=src)
    assert not dest.exists()


def test_output_size_mismatch_rejected_before_crops(tmp_path):
    src, v2, super_img = (tmp_path / p for p in ("src.png", "v2.png", "super.png"))
    Image.new("RGB", (10, 10)).save(src)
    Image.new("RGB", (20, 20)).save(v2)
    Image.new("RGB", (21, 20)).save(super_img)
    dest = tmp_path / "qa"
    with pytest.raises(ValueError, match="different output pixel dimensions"):
        run_audit(src, _regions(tmp_path / "regions.json"), dest,
                  v2=v2, super_path=super_img)
    assert not dest.exists()
