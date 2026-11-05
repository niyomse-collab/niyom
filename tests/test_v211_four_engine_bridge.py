"""The four-engine bridge must be opt-in and must never rewrite V2."""
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from signprint_ai import v211_four_engine_bridge as bridge


def _images(tmp_path):
    src = tmp_path / "source.png"
    baseline = tmp_path / "V2.png"
    Image.new("RGBA", (8, 8), (20, 30, 40, 120)).save(src)
    Image.new("RGBA", (16, 16), (30, 40, 50, 120)).save(baseline)
    return src, baseline


def test_default_disabled_preserves_print_output(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "0")
    assert bridge.maybe_run_four_engine_assist(source, baseline)["status"] == "disabled"
    assert baseline.read_bytes() == old


def test_missing_model_manifest_is_non_destructive(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "not-installed"))
    assert bridge.maybe_run_four_engine_assist(source, baseline)["status"] == "models_not_installed"
    assert baseline.read_bytes() == old


def test_disabled_for_non_ai_jobs(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    assert bridge.maybe_run_four_engine_assist(source, baseline, use_ai=False)["status"] == "disabled"


def test_non_raster_output_keeps_v2(tmp_path, monkeypatch):
    source, _ = _images(tmp_path)
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"unchanged-print-export")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", "test-manifest.json")
    assert bridge.maybe_run_four_engine_assist(source, pdf)["status"] == "unsupported_output_format"
    assert pdf.read_bytes() == b"unchanged-print-export"


def test_fake_runner_cannot_replace_v2_output(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run
    calls = []
    def stub(src, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(src) as seed, Image.open(v2_reference) as reference:
            calls.append((seed.size, reference.size, size, real_engines))
        return {"ready_for_fusion_research": True, "completed_engine_count": 4, "failures": {}}
    monkeypatch.setattr(v211_four_engine_run, "run", stub)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "candidate_research_complete"
    assert result["quality_certified"] is False
    assert result["fusion_implemented"] is False
    assert result["v2_output_preserved"]
    assert calls == [((8, 8), (16, 16), (16, 16), True)]
    assert baseline.read_bytes() == old


def test_faulty_engine_does_not_fail_v2_job(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", "manifest.json")
    from tools import v211_four_engine_run
    def broken(*args, **kwargs):
        raise RuntimeError("GPU device lost")
    monkeypatch.setattr(v211_four_engine_run, "run", broken)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "error"
    assert baseline.read_bytes() == old


@pytest.mark.parametrize(
    ("target_size", "expected_seed", "expected_padded"),
    [
        ((16, 16), (8, 8), (16, 16)),
        ((32, 32), (16, 16), (32, 32)),
        ((64, 64), (32, 32), (64, 64)),
        ((31, 23), (16, 12), (32, 24)),
    ],
)
def test_native_2x_engines_support_custom_and_4x_8x_target_sizes(
    tmp_path, monkeypatch, target_size, expected_seed, expected_padded
):
    source, baseline = _images(tmp_path)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGBA", target_size, (30, 40, 50, 120)).save(
        baseline, dpi=(300, 300), icc_profile=icc
    )
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run
    calls = []

    def fake_run(src, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(src) as seed, Image.open(v2_reference) as reference:
            calls.append((seed.size, reference.size, size, real_engines))
            fused = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {"fusion_implemented": True, "all_four_engine_pixels_contributed": True, "output": str(fused)},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "four_engine_fusion_preview_ready"
    assert result["quality_certified"] is False
    assert result["v2_output_preserved"] is True
    assert result["four_engine_fusion_details"]["native_engine_scale"] == 2
    assert result["four_engine_fusion_details"]["scale_policy"] == "native_2x_on_half_target_seed"
    assert calls == [(expected_seed, expected_padded, expected_padded, True)]
    assert baseline.read_bytes() == before
    preview = Path(result["four_engine_fusion_output"])
    with Image.open(preview) as image, Image.open(baseline) as reference:
        assert image.size == target_size
        assert image.mode == "RGBA"
        assert image.getchannel("A").tobytes() == reference.getchannel("A").tobytes()
        assert image.info.get("icc_profile") == icc


def test_rgb_tiff_v2_output_gets_local_png_qa_without_modifying_tiff(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-V2.tiff"
    Image.new("RGB", (8, 8), (20, 30, 40)).save(source)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (32, 24), (30, 40, 50)).save(
        baseline, dpi=(300, 300), icc_profile=icc
    )
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run

    def fake_run(src, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(v2_reference) as reference:
            fused = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {"fusion_implemented": True, "all_four_engine_pixels_contributed": True, "output": str(fused)},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "four_engine_fusion_preview_ready"
    assert baseline.read_bytes() == before
    preview = Path(result["four_engine_fusion_output"])
    assert preview.suffix == ".png" and ".V211-4AI-QA-" in preview.name
    with Image.open(preview) as image:
        assert image.size == (32, 24)
        assert image.info.get("icc_profile") == icc


def test_fusion_with_missing_engine_pixel_effect_is_not_reported_ready(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run

    def fake_run(src, output_dir, manifest, size, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        fused = output_dir / "four_engine_fused_preview.png"
        Image.new("RGBA", size, (210, 20, 40, 120)).save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": False,
                "engine_pixel_effect_verified": {
                    "real_esrgan": True, "waifu2x": True,
                    "real_cugan": True, "anime4k": False,
                },
                "engine_pixel_effect_pixels": {
                    "real_esrgan": 12, "waifu2x": 9,
                    "real_cugan": 10, "anime4k": 0,
                },
                "output": str(fused),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "four_engine_fusion_contribution_incomplete"
    assert result["all_four_engine_pixels_contributed"] is False
    assert result["engine_pixel_effect_verified"]["anime4k"] is False
    assert Path(result["four_engine_fusion_output"]).is_file()
    assert baseline.read_bytes() == before


def test_opt_in_three_primary_candidates_do_not_require_anime_preview(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run

    def fake_run(*args, **kwargs):
        return {
            "ready_for_fusion_research": False,
            "completed_engine_count": 3,
            "failures": {"anime4k": "optional engine unavailable"},
            "three_engine_priority_preview": {
                "selected": "real_cugan",
                "output": "/private/tmp/deleted-preview.png",
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "three_engine_priority_preview_ready"
    assert result["priority_preview_selected"] == "real_cugan"
    assert result["priority_preview_path"] is None  # temp folder was deleted
    assert result["quality_certified"] is False
    assert result["v2_output_preserved"]
    assert baseline.read_bytes() == before



def test_cancelled_native_run_cleans_persistent_private_evidence(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    evidence = tmp_path / "private-evidence"
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", str(evidence))
    from tools import v211_four_engine_run

    cancel = lambda: False

    def cancelled_run(src, output_dir, manifest, size, **kwargs):
        assert kwargs["cancel"] is cancel
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "partial-candidate.png").write_bytes(b"private partial")
        raise InterruptedError("Processing stopped by user")

    monkeypatch.setattr(v211_four_engine_run, "run", cancelled_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline, cancel=cancel)
    assert result["status"] == "cancelled"
    assert result["v2_output_preserved"] is True
    assert baseline.read_bytes() == before
    assert evidence.is_dir()
    assert list(evidence.iterdir()) == []



def test_late_cancel_after_sidecar_copy_removes_qa_file_and_keeps_v2(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run

    def fake_run(src, output_dir, manifest, size, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        fused = output_dir / "four_engine_fused_preview.png"
        Image.new("RGBA", size, (210, 20, 40, 120)).save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    checks = {"count": 0}

    def cancel_after_copy():
        checks["count"] += 1
        return checks["count"] >= 3

    result = bridge.maybe_run_four_engine_assist(
        source, baseline, cancel=cancel_after_copy
    )
    assert result["status"] == "cancelled"
    assert result["v2_output_preserved"] is True
    assert baseline.read_bytes() == before
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


@pytest.mark.parametrize(
    ("resize_mode", "expected_top_pixel", "expected_center_pixel"),
    [
        ("fit", (255, 255, 255), (220, 30, 40)),
        ("stretch", (220, 30, 40), (220, 30, 40)),
    ],
)
def test_native_seed_uses_the_same_fit_or_stretch_geometry_as_v2(
    tmp_path, resize_mode, expected_top_pixel, expected_center_pixel
):
    source = tmp_path / "wide-source.png"
    baseline = tmp_path / "V2-fit-reference.png"
    Image.new("RGB", (8, 4), (220, 30, 40)).save(source)
    reference = Image.new("RGB", (16, 16), (255, 255, 255))
    if resize_mode == "fit":
        reference.paste(Image.new("RGB", (16, 8), (220, 30, 40)), (0, 4))
    else:
        reference = Image.new("RGB", (16, 16), (220, 30, 40))
    reference.save(baseline)

    seed_path, reference_path, target_size, padded_size, source_size, _ = (
        bridge._prepare_native_2x_inputs(
            source, baseline, tmp_path / "native-work", resize_mode=resize_mode
        )
    )
    with Image.open(seed_path) as seed, Image.open(reference_path) as saved_reference:
        assert seed.size == (8, 8)
        assert seed.getpixel((4, 0)) == expected_top_pixel
        assert seed.getpixel((4, 3)) == expected_center_pixel
        assert saved_reference.size == padded_size == (16, 16)
    assert target_size == (16, 16)
    assert source_size == (8, 4)
