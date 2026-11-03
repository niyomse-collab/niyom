"""Unit tests for *true* HR (not bicubic 1x) V2.1.1 acceptance evidence."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.v211_true_hr_benchmark import (
    _psnr, _regions, degrade_to_low_resolution, evaluate_true_hr,
    make_ground_truth, run
)


def test_true_hr_is_drawn_first_and_low_res_is_reproducibly_degraded():
    truth = make_ground_truth((192, 192))
    noisy = degrade_to_low_resolution(truth)
    assert truth.shape == (192, 192, 3)
    assert noisy.shape == (96, 96, 3)
    np.testing.assert_array_equal(noisy, degrade_to_low_resolution(truth))
    assert len(np.unique(truth.reshape(-1, 3), axis=0)) > 100
    plain_down = np.asarray(Image.fromarray(truth).resize(
        (96, 96), Image.Resampling.LANCZOS))
    assert np.mean(np.abs(noisy.astype("float32") - plain_down)) > 4


def test_true_hr_regions_have_distinct_photo_edge_and_ink_area():
    truth = make_ground_truth()
    regions = _regions(truth)
    for name in ("overall", "photo_texture", "graphic_edges", "flat_ink"):
        assert regions[name].shape == (192, 192)
        assert regions[name].sum() >= 50
    assert not np.array_equal(regions["photo_texture"], regions["graphic_edges"])


def test_no_phantom_quality_leap_from_an_identical_output():
    truth = make_ground_truth()
    baseline = np.clip(truth.astype(np.int16) + 12, 0, 255).astype("uint8")
    result = evaluate_true_hr(truth, baseline, baseline.copy())
    assert result["overall"]["gain_db"] == 0
    assert result["provisional_quality_screen_pass"] is False
    assert result["image_quality_certified"] is False


def test_quality_screen_detects_true_gain_against_independent_hr():
    truth = make_ground_truth()
    baseline = np.clip(truth.astype(np.int16) + 15, 0, 255).astype("uint8")
    better = np.clip(truth.astype(np.int16) + 5, 0, 255).astype("uint8")
    outcome = evaluate_true_hr(truth, baseline, better)
    assert outcome["provisional_quality_screen_pass"] is True
    assert outcome["overall"]["gain_db"] > 5
    assert outcome["image_quality_certified"] is False


def test_improving_photo_but_damaging_text_ink_cannot_pass():
    truth = make_ground_truth()
    baseline = np.clip(truth.astype(np.int16) + 12, 0, 255).astype("uint8")
    candidate = np.clip(truth.astype(np.int16) + 3, 0, 255).astype("uint8")
    candidate[_regions(truth)["graphic_edges"]] = np.clip(
        candidate[_regions(truth)["graphic_edges"]].astype(np.int16) + 35,
        0, 255
    ).astype("uint8")
    outcome = evaluate_true_hr(truth, baseline, candidate)
    assert outcome["photo_texture"]["gain_db"] > 1
    assert outcome["graphic_edges"]["gain_db"] < 0
    assert outcome["provisional_quality_screen_pass"] is False


def test_reject_incompatible_comparison_geometry():
    truth = make_ground_truth()
    with pytest.raises(ValueError, match="equal dimensions"):
        _psnr(truth, truth[:100])


class ResearchAdapter:
    def selected_model_available(self, name):
        return name == "v2_swinir_pre"

    def process(self, source, destination, settings, *, use_ai):
        assert use_ai and settings.ai_scale == 2
        with Image.open(source) as image:
            out = image.convert("RGB").resize(
                (image.width*2, image.height*2), Image.Resampling.BICUBIC
            )
        out.save(destination, dpi=(300, 300))
        return {"model": ("V2 RealESRGAN_x4plus + SwinIR pre-denoise"
                          if settings.v211_photo_model == "v2_swinir_pre"
                          else "RealESRGAN_x4plus")}


def test_full_benchmark_writes_true_hr_and_distinguishes_metrics(tmp_path):
    report = run(tmp_path/"qa", adapter=ResearchAdapter())
    assert report["provisional_quality_screen_pass"] is False
    assert report["overall"]["gain_db"] == 0
    assert report["reference_type"] == "independently rendered synthetic true-HR"
    assert report["image_quality_certified"] is False
    assert (tmp_path/"qa"/"TRUE_HIGH_RES_REFERENCE.png").is_file()
    assert (tmp_path/"qa"/"DEGRADED_LOW_RES_SOURCE.png").is_file()
    assert (tmp_path/"qa"/"TRUE_HR_BENCHMARK.json").is_file()
