"""Regression guards for the deliberately low-authority Anime4K fusion role.

These tests use synthetic candidate rasters only. They test the fusion policy,
not native model inference or visual quality.
"""
import numpy as np
from PIL import Image

from tools.v211_four_engine_coordinator import ENGINES
from tools.v211_four_engine_fusion import fuse_four_engine_details


def _save(path, pixels):
    Image.fromarray(pixels, "RGB").save(path, dpi=(300, 300))


def _fixture(tmp_path):
    source = tmp_path / "source.png"
    baseline = tmp_path / "v2.png"
    source_pixels = np.full((8, 8, 3), 70, dtype=np.uint8)
    base = np.empty((16, 16, 3), dtype=np.uint8)
    base[:, :8] = (70, 70, 70)
    base[:, 8:] = (170, 170, 170)
    _save(source, source_pixels)
    _save(baseline, base)

    candidates = {}
    for name, amount in (
        ("real_esrgan", 9),
        ("waifu2x", 7),
        ("real_cugan", 8),
        ("anime4k", 5),
    ):
        pixels = base.copy()
        pixels[:, 7] -= amount
        pixels[:, 8] += amount
        path = tmp_path / f"{name}.png"
        _save(path, pixels)
        candidates[name] = path
    return source, baseline, base, candidates


def _fuse(source, baseline, candidates, output):
    return fuse_four_engine_details(source, baseline, candidates, output)


def test_anime4k_detail_is_bounded_to_at_most_one_output_level(tmp_path):
    """The 0.06 Anime4K term may refine primary consensus, never dominate it."""
    source, baseline, base, candidates = _fixture(tmp_path)
    with_anime = tmp_path / "with-anime.png"
    report = _fuse(source, baseline, candidates, with_anime)

    primary_only = dict(candidates)
    no_anime = tmp_path / "anime-neutral.png"
    _save(no_anime, base)
    primary_only["anime4k"] = no_anime
    without_anime = tmp_path / "without-anime.png"
    _fuse(source, baseline, primary_only, without_anime)

    with Image.open(with_anime) as actual, Image.open(without_anime) as control:
        delta = np.abs(
            np.asarray(actual, dtype=np.int16)
            - np.asarray(control, dtype=np.int16)
        )
    assert int(delta.max()) <= 1
    assert report["engine_pixel_effect_verified"]["anime4k"] is True
    assert report["engine_detail_contribution_mean_abs"]["anime4k"] > 0


def test_anime4k_out_of_range_detail_is_ignored(tmp_path):
    """A strong Anime4K-only contour cannot bypass the <=9 luminance-delta gate."""
    source, baseline, base, candidates = _fixture(tmp_path)
    control_candidates = dict(candidates)
    neutral = tmp_path / "anime-neutral.png"
    _save(neutral, base)
    control_candidates["anime4k"] = neutral

    extreme = base.copy()
    extreme[:, 7] = (0, 0, 0)
    extreme[:, 8] = (255, 255, 255)
    hostile = tmp_path / "anime-extreme.png"
    _save(hostile, extreme)
    candidates["anime4k"] = hostile

    actual_path = tmp_path / "extreme-result.png"
    report = _fuse(source, baseline, candidates, actual_path)
    control_path = tmp_path / "neutral-result.png"
    _fuse(source, baseline, control_candidates, control_path)

    with Image.open(actual_path) as actual, Image.open(control_path) as control:
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(control))
    assert report["engine_pixel_effect_verified"]["anime4k"] is False
    assert report["engine_pixel_effect_pixels"]["anime4k"] == 0
    assert all(
        report["engine_pixel_effect_verified"][name]
        for name in ("real_esrgan", "waifu2x", "real_cugan")
    )


def test_anime4k_cannot_create_consensus_without_primary_engines(tmp_path):
    """Anime4K alone cannot activate an edge or change accepted V2 pixels."""
    source, baseline, base, candidates = _fixture(tmp_path)
    for name in ("real_esrgan", "waifu2x", "real_cugan"):
        neutral = tmp_path / f"{name}-neutral.png"
        _save(neutral, base)
        candidates[name] = neutral

    output = tmp_path / "anime-only.png"
    report = _fuse(source, baseline, candidates, output)
    with Image.open(output) as result:
        np.testing.assert_array_equal(np.asarray(result), base)

    assert report["all_four_engine_candidates_consumed"] is True
    assert report["all_four_engine_pixels_contributed"] is False
    assert not any(report["engine_pixel_effect_verified"].values())
    assert all(report["engine_pixel_effect_pixels"][name] == 0 for name in ENGINES)
