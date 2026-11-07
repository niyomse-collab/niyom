"""Pixel evidence for four-engine fusion; fake images are NOT model inference."""
import numpy as np
import zlib
import pytest
from PIL import Image

from tools.v211_four_engine_fusion import fuse_four_engine_details
from tools.v211_four_engine_coordinator import ENGINES


def _fixture(tmp_path, rgba=False, dpi=300):
    source = tmp_path / "original.png"
    baseline = tmp_path / "v2.png"
    mode = "RGBA" if rgba else "RGB"
    small = np.zeros((8, 8, 4 if rgba else 3), dtype=np.uint8)
    small[..., :3] = 70
    small[:, 4:, :3] = 170
    if rgba:
        small[..., 3] = 255
    Image.fromarray(small, mode).save(source, dpi=(dpi, dpi))
    large = np.zeros((16, 16, small.shape[2]), dtype=np.uint8)
    large[..., :3] = 70
    large[:, 8:, :3] = 170
    if rgba:
        large[..., 3] = 255
    Image.fromarray(large, mode).save(baseline, dpi=(dpi, dpi))
    candidates = {}
    for name, amount in (("real_esrgan", 9), ("waifu2x", 7), ("real_cugan", 8), ("anime4k", 5)):
        pix = large.copy()
        # All models agree on a cleaner, tighter contrast boundary.
        pix[:, 7, :3] -= amount
        pix[:, 8, :3] += amount
        path = tmp_path / (name + ".png")
        Image.fromarray(pix, mode).save(path, dpi=(dpi, dpi))
        candidates[name] = path
    return source, baseline, candidates


def test_four_models_fuse_to_separate_png_and_keep_v2_exact(tmp_path):
    source, baseline, candidates = _fixture(tmp_path)
    original = baseline.read_bytes()
    output = tmp_path / "fused.png"
    report = fuse_four_engine_details(source, baseline, candidates, output)
    assert report["fusion_implemented"] is True
    assert report["all_four_engine_candidates_consumed"] is True
    assert report["all_four_engine_pixels_contributed"] is True
    assert all(report["engine_pixel_effect_verified"].values())
    assert all(report["engine_pixel_effect_pixels"][name] > 0 for name in ENGINES)
    assert report["contribution_attribution"].startswith("leave_one_engine_out")
    assert report["experimental_preview_only"] is True
    assert report["quality_certified"] is False
    assert report["edge_pixels_modified_or_considered"] > 0
    assert report["mean_abs_detail_delta"] > 0
    assert report["engine_detail_contribution_mean_abs"]["real_cugan"] > 0
    assert report["engine_detail_contribution_mean_abs"]["waifu2x"] > 0
    assert report["engine_detail_contribution_mean_abs"]["real_esrgan"] > 0
    assert report["engine_detail_contribution_mean_abs"]["anime4k"] > 0
    assert baseline.read_bytes() == original
    with Image.open(baseline) as base, Image.open(output) as fused:
        v2 = np.asarray(base).copy()
        im = np.asarray(fused)
        assert np.any(v2 != im)
        # Flat print background and gradient-independent areas remain exact V2.
        np.testing.assert_array_equal(im[:, :4], v2[:, :4])
        assert fused.info["dpi"][0] == pytest.approx(300, abs=0.1)
        assert int(np.abs(im.astype(int) - v2.astype(int)).max()) <= 6


def test_engine_without_counterfactual_pixel_effect_is_not_counted(tmp_path):
    src, v2, candidates = _fixture(tmp_path)
    with Image.open(v2) as base:
        base.copy().save(candidates["anime4k"], dpi=(300, 300))
    report = fuse_four_engine_details(
        src, v2, candidates, tmp_path / "incomplete-contribution.png"
    )
    assert report["fusion_implemented"] is True
    assert report["all_four_engine_candidates_consumed"] is True
    assert report["all_four_engine_pixels_contributed"] is False
    assert report["engine_pixel_effect_verified"]["anime4k"] is False
    assert report["engine_pixel_effect_pixels"]["anime4k"] == 0
    assert all(
        report["engine_pixel_effect_verified"][name]
        for name in ("real_esrgan", "waifu2x", "real_cugan")
    )


def test_rgba_keeps_identical_alpha_and_transparent_edges(tmp_path):
    src, v2, cands = _fixture(tmp_path, rgba=True)
    output = tmp_path / "rgba-fused.png"
    fuse_four_engine_details(src, v2, cands, output)
    with Image.open(v2) as base, Image.open(output) as fused:
        assert fused.mode == "RGBA"
        np.testing.assert_array_equal(np.asarray(base.getchannel("A")), np.asarray(fused.getchannel("A")))


def test_rgba_fusion_preserves_rgb_under_transparent_and_antialiased_edges(tmp_path):
    src, v2, cands = _fixture(tmp_path, rgba=True)
    with Image.open(v2) as base:
        pixels = np.asarray(base).copy()
    # Model candidates alter the existing high-contrast contour at columns 7/8.
    # Make one pixel column antialiased and the next fully transparent in V2.
    pixels[:, 7, 3] = 128
    pixels[:, 8, 3] = 0
    Image.fromarray(pixels, "RGBA").save(v2, dpi=(300, 300))

    output = tmp_path / "rgba-edge-safe.png"
    fuse_four_engine_details(src, v2, cands, output)
    with Image.open(v2) as base, Image.open(output) as fused:
        original = np.asarray(base)
        result = np.asarray(fused)
        np.testing.assert_array_equal(result[..., 3], original[..., 3])
        protected = original[..., 3] < 255
        np.testing.assert_array_equal(result[..., :3][protected], original[..., :3][protected])


def test_face_protection_region_copies_v2_pixel_for_pixel(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    output = tmp_path / "faces.png"
    report = fuse_four_engine_details(
        src, v2, cands, output,
        protected_regions=((0.25, 0.0, 0.75, 1.0),),
    )
    assert report["protected_faces_preserved"]
    with Image.open(v2) as base, Image.open(output) as result:
        np.testing.assert_array_equal(np.asarray(base), np.asarray(result))


def test_auto_face_without_rectangles_keeps_complete_v2(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    result = fuse_four_engine_details(src, v2, cands, tmp_path / "portrait.png",
                                      preserve_all_v2_faces=True)
    assert result["protected_faces_preserved"]
    assert result["mean_abs_detail_delta"] == 0
    assert result["all_four_engine_pixels_contributed"] is False
    assert not any(result["engine_pixel_effect_verified"].values())
    with Image.open(v2) as base, Image.open(tmp_path / "portrait.png") as fused:
        np.testing.assert_array_equal(np.asarray(base), np.asarray(fused))


def test_missing_engine_fails_closed(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    cands.pop("anime4k")
    with pytest.raises(ValueError, match="four independent"):
        fuse_four_engine_details(src, v2, cands, tmp_path / "blocked.png")
    assert not (tmp_path / "blocked.png").exists()


def test_never_overwrite_approved_v2_or_source(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    with pytest.raises(ValueError, match="may not overwrite"):
        fuse_four_engine_details(src, v2, cands, v2)
    with pytest.raises(ValueError, match="may not overwrite"):
        fuse_four_engine_details(src, v2, cands, src)


def test_reject_candidate_wrong_alpha(tmp_path):
    src, v2, cands = _fixture(tmp_path, rgba=True)
    with Image.open(cands["anime4k"]) as im:
        pix = np.asarray(im).copy()
    pix[0, 0, 3] = 0
    Image.fromarray(pix, "RGBA").save(cands["anime4k"])
    with pytest.raises(ValueError, match="alpha|transparency|RGBA"):
        fuse_four_engine_details(src, v2, cands, tmp_path / "bad-alpha.png")


def test_reject_mismatched_size(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    Image.new("RGB", (14, 16)).save(cands["waifu2x"])
    with pytest.raises(ValueError, match="dimensions"):
        fuse_four_engine_details(src, v2, cands, tmp_path / "bad-geometry.png")


def test_saturated_edge_keeps_channel_differences_without_clipping(tmp_path):
    """Synthetic candidates only: shared luminance must not shift saturated hue."""
    src, v2, cands = _fixture(tmp_path)
    with Image.open(v2) as im:
        pix = np.asarray(im).copy()
    # A bright saturated boundary has no upward headroom in red.
    pix[:, :8, :3] = (255, 70, 30)
    pix[:, 8:, :3] = (245, 170, 130)
    Image.fromarray(pix, "RGB").save(v2, dpi=(300, 300))
    for name, path in cands.items():
        candidate = pix.copy()
        amount = 9 if name != "anime4k" else 5
        candidate[:, 7, :3] = np.clip(candidate[:, 7, :3].astype(int) - amount, 0, 255)
        candidate[:, 8, :3] = np.clip(candidate[:, 8, :3].astype(int) + amount, 0, 255)
        Image.fromarray(candidate, "RGB").save(path, dpi=(300, 300))
    output = tmp_path / "saturated.png"
    fuse_four_engine_details(src, v2, cands, output)
    with Image.open(output) as im:
        result = np.asarray(im).astype(int)
    baseline = pix.astype(int)
    change = result - baseline
    # Common luminance change is identical in all RGB channels at every pixel.
    np.testing.assert_array_equal(change[..., 0], change[..., 1])
    np.testing.assert_array_equal(change[..., 1], change[..., 2])
    assert np.max(np.abs(change)) <= 6


def test_four_x_fusion_accepts_exact_geometry_and_preserves_v2(tmp_path):
    """Synthetic 4x inputs exercise geometry, not actual native inference."""
    src, v2, cands = _fixture(tmp_path, rgba=True)
    with Image.open(v2) as im:
        four_x = im.resize((32, 32), Image.Resampling.NEAREST)
        four_x.save(v2, dpi=(300, 300))
    for path in cands.values():
        with Image.open(path) as im:
            im.resize((32, 32), Image.Resampling.NEAREST).save(path, dpi=(300, 300))
    original_bytes = v2.read_bytes()
    output = tmp_path / "four-x-fusion.png"
    report = fuse_four_engine_details(src, v2, cands, output)
    assert report["quality_certified"] is False
    assert v2.read_bytes() == original_bytes
    with Image.open(v2) as base, Image.open(output) as fused:
        assert fused.size == (32, 32)
        np.testing.assert_array_equal(np.asarray(base.getchannel("A")),
                                      np.asarray(fused.getchannel("A")))
        assert fused.info["dpi"][0] == pytest.approx(300, abs=0.1)


def test_fusion_rejects_non_integer_scale(tmp_path):
    src, v2, cands = _fixture(tmp_path)
    with Image.open(v2) as im:
        im.resize((24, 24)).save(v2)
    with pytest.raises(ValueError, match="2x or 4x"):
        fuse_four_engine_details(src, v2, cands, tmp_path / "invalid-scale.png")



def test_cancel_between_fusion_tiles_leaves_no_partial_qa_file(tmp_path, monkeypatch):
    from tools import v211_four_engine_fusion as fusion
    src, v2, cands = _fixture(tmp_path)
    output = tmp_path / "cancelled-fusion.png"
    monkeypatch.setattr(fusion, "TILE", 8)
    checks = {"count": 0}

    def cancel_after_first_tile():
        checks["count"] += 1
        return checks["count"] >= 2

    with pytest.raises(InterruptedError, match="stopped"):
        fusion.fuse_four_engine_details(
            src, v2, cands, output, cancel_check=cancel_after_first_tile
        )
    assert checks["count"] == 2
    assert not output.exists()


def test_over_18mp_fusion_fails_closed_from_png_header_without_decode(tmp_path):
    """A large master must not reach Pillow's full-image crop/allocation path."""
    src, _baseline, candidates = _fixture(tmp_path)
    large = tmp_path / "large-v2.png"
    ihdr = (
        (6_000).to_bytes(4, "big") + (4_000).to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    chunk = b"IHDR" + ihdr
    header = (
        b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big")
        + chunk + (zlib.crc32(chunk) & 0xFFFFFFFF).to_bytes(4, "big")
    )
    large.write_bytes(header)
    output = tmp_path / "large-fusion.png"

    with pytest.raises(RuntimeError, match="disk-backed streaming"):
        fuse_four_engine_details(src, large, candidates, output)

    assert not output.exists()
    assert large.read_bytes() == header
