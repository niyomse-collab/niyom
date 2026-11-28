"""The four-engine bridge must be opt-in and must never rewrite V2."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageFile, PngImagePlugin

from signprint_ai import v211_four_engine_bridge as bridge
from tools.v211_gpu_device_binding import GPUDeviceBindingError


@pytest.fixture(autouse=True)
def _stub_runtime_device_binding(monkeypatch):
    def prepare(_manifest_path, work_dir):
        bound = Path(work_dir) / "manifest.runtime-bound.json"
        bound.write_text("{}", encoding="utf-8")
        return bound, {
            "binding_configured": True,
            "runtime_device_use_verified": False,
            "ncnn_vulkan": {"device_index": 2, "device_name": "NVIDIA GeForce GTX 1660 Ti"},
            "anime4k": {"backend": "cuda", "device_index": 1,
                        "device_name": "NVIDIA GeForce GTX 1660 Ti"},
        }
    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", prepare)


def _images(tmp_path):
    src = tmp_path / "source.png"
    baseline = tmp_path / "V2.png"
    Image.new("RGBA", (8, 8), (20, 30, 40, 120)).save(src)
    Image.new("RGBA", (16, 16), (30, 40, 50, 120)).save(baseline)
    return src, baseline


def test_gpu_binding_failure_blocks_native_runner_and_preserves_v2(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))

    def blocked(_manifest, _work_dir):
        raise GPUDeviceBindingError("ambiguous GTX 1660 Ti Vulkan index")

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", blocked)
    from tools import v211_four_engine_run

    def must_not_run(*args, **kwargs):
        pytest.fail("native engines must not run without a verified device binding")

    monkeypatch.setattr(v211_four_engine_run, "run", must_not_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_binding_unverified"
    assert "ambiguous" in result["reason"]
    assert result["v2_output_preserved"] is True
    assert baseline.read_bytes() == before


def test_default_disabled_preserves_print_output(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "0")
    assert bridge.maybe_run_four_engine_assist(source, baseline)["status"] == "disabled"
    assert baseline.read_bytes() == old


def test_bridge_rejects_source_v2_rgb_rgba_mismatch_before_gpu_binding(
    tmp_path, monkeypatch
):
    source = tmp_path / "transparent-source.png"
    baseline = tmp_path / "rgb-v2.png"
    Image.new("RGBA", (128, 96), (20, 30, 40, 128)).save(source)
    Image.new("RGB", (256, 192), (30, 40, 50)).save(baseline)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))

    def forbidden(*_args, **_kwargs):
        pytest.fail("mode mismatch must stop before GPU binding or native launch")

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", forbidden)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "source_output_mode_mismatch"
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert baseline.read_bytes() == before
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


@pytest.mark.parametrize(
    ("source_mode", "v2_mode"),
    [("RGBA", "RGB"), ("RGB", "RGBA")],
)
def test_small_and_large_seed_paths_reject_rgb_rgba_mode_mismatch_before_writing(
    tmp_path, source_mode, v2_mode
):
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    source = tmp_path / "mode-mismatch-source.png"
    baseline = tmp_path / "mode-mismatch-v2.png"
    source_pixel = (20, 30, 40, 128) if source_mode == "RGBA" else (20, 30, 40)
    v2_pixel = (30, 40, 50, 128) if v2_mode == "RGBA" else (30, 40, 50)
    Image.new(source_mode, (128, 96), source_pixel).save(source)
    Image.new(v2_mode, (256, 192), v2_pixel).save(baseline)

    for prepare, folder in (
        (bridge._prepare_native_2x_inputs, "small-mode-mismatch"),
        (prepare_native_2x_inputs_streamed, "large-mode-mismatch"),
    ):
        work_dir = tmp_path / folder
        with pytest.raises(ValueError, match="matching RGB/RGBA mode"):
            prepare(source, baseline, work_dir)
        assert not work_dir.exists()




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


def test_styled_effect_regions_are_forwarded_to_fusion_runner(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    regions = ((0.12, 0.18, 0.72, 0.84),)
    result = bridge.maybe_run_four_engine_assist(
        source, baseline, protected_effect_regions=regions
    )
    assert captured["protected_effect_regions"] == regions
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False


def test_effect_roi_mapping_validates_and_uses_the_v2_resize_transform():
    stretch = bridge.map_protected_effect_regions(
        ((0.1, 0.2, 0.7, 0.8),), (100, 50), (300, 300), "stretch"
    )
    assert stretch == ((0.1, 0.2, 0.7, 0.8),)
    fit = bridge.map_protected_effect_regions(
        ((0.25, 0.2, 0.75, 0.8),), (200, 100), (200, 200), "fit"
    )
    assert fit == ((0.25, 0.35, 0.75, 0.65),)


@pytest.mark.parametrize(
    "regions",
    [
        "not-a-list",
        ((-0.1, 0.2, 0.7, 0.8),),
        ((0.1, 0.2, 0.1, 0.8),),
        ((0.1, 0.2, float("nan"), 0.8),),
        ((0.1, 0.2, 0.7),),
    ],
)
def test_invalid_effect_roi_mapping_fails_closed(regions):
    with pytest.raises(ValueError):
        bridge.map_protected_effect_regions(
            regions, (100, 50), (300, 300), "stretch"
        )


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
        ((16, 16), (8, 8), (16, 16)),       # exact 2x
        ((24, 24), (12, 12), (24, 24)),     # exact 3x via half-target seed
        ((32, 32), (16, 16), (32, 32)),     # exact 4x via half-target seed
        ((32, 24), (16, 12), (32, 24)),    # anisotropic 4x by 3x
        ((64, 64), (32, 32), (64, 64)),    # 8x source-to-print via one native 2x pass
        ((25, 17), (13, 9), (26, 18)),     # custom odd dimensions, edge-padded
    ],
)
def test_native_2x_engines_use_half_target_seed_for_custom_target_geometry(
    tmp_path, monkeypatch, target_size, expected_seed, expected_padded
):
    source, baseline = _images(tmp_path)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    tagged_source = tmp_path / "source-tagged.png"
    with Image.open(source) as source_image:
        source_image.save(tagged_source, dpi=(300, 300), icc_profile=icc)
    source = tagged_source
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
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
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
    assert result["four_engine_fusion_details"]["requested_scale_from_source"] == [
        round(target_size[0] / 8, 4), round(target_size[1] / 8, 4)
    ]
    assert baseline.read_bytes() == before
    preview = Path(result["four_engine_fusion_output"])
    with Image.open(preview) as image, Image.open(baseline) as reference:
        assert image.size == target_size
        assert image.mode == "RGBA"
        assert image.getchannel("A").tobytes() == reference.getchannel("A").tobytes()
        assert image.info.get("icc_profile") == icc



@pytest.mark.parametrize("target_size", [(1, 1), (2, 4), (4, 2)])
def test_too_small_half_target_seed_is_rejected_before_gpu_binding_or_native_launch(
    tmp_path, monkeypatch, target_size
):
    source = tmp_path / "source.png"
    baseline = tmp_path / "V2.png"
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGBA", (8, 8), (20, 30, 40, 120)).save(
        source, dpi=(300, 300), icc_profile=icc
    )
    Image.new("RGBA", target_size, (30, 40, 50, 120)).save(
        baseline, dpi=(300, 300), icc_profile=icc
    )
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST",
        str(tmp_path / "manifest.json"),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("too-small target must be rejected before GPU binding or native launch")

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", forbidden)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "unsupported_target_geometry"
    assert result["reason"] == "half_target_seed_must_be_at_least_2x2"
    assert result["v2_output_preserved"] is True
    assert baseline.read_bytes() == before

def test_rgb_tiff_v2_output_gets_local_png_qa_without_modifying_tiff(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-V2.tiff"
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    # Exact 4x geometry: the native engine receives a half-target 2x seed.
    Image.new("RGB", (8, 6), (20, 30, 40)).save(
        source, dpi=(300, 300), icc_profile=icc
    )
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
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
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


@pytest.mark.parametrize(
    ("target_size", "expected_seed"),
    [((16, 16), (8, 8)), ((64, 64), (32, 32))],
)
def test_fusion_with_missing_engine_pixel_effect_is_not_reported_ready(
    tmp_path, monkeypatch, target_size, expected_seed
):
    source, baseline = _images(tmp_path)
    if target_size != (16, 16):
        Image.new("RGBA", target_size, (30, 40, 50, 120)).save(baseline)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run
    observed = {}

    def fake_run(src, output_dir, manifest, size, **kwargs):
        with Image.open(src) as seed:
            observed["seed_size"] = seed.size
        assert tuple(size) == target_size
        output_dir.mkdir(parents=True, exist_ok=True)
        fused = output_dir / "four_engine_fused_preview.png"
        Image.new("RGBA", size, (210, 20, 40, 120)).save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
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
    assert observed["seed_size"] == expected_seed
    assert result["status"] == "four_engine_fusion_contribution_incomplete"
    assert result["all_four_engine_pixels_contributed"] is False
    assert result["engine_pixel_effect_verified"]["anime4k"] is False
    assert result["four_engine_fusion_output"] is None
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))
    assert baseline.read_bytes() == before


def test_deleted_three_engine_preview_is_not_reported_ready(tmp_path, monkeypatch):
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
    assert result["status"] == "incomplete_four_engine_candidates"
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
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
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

def test_oversized_target_is_rejected_before_full_image_copy(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    Image.new("RGB", (9, 8), (30, 40, 50)).save(baseline)
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 64)
    work_dir = tmp_path / "must-not-be-created"

    def no_full_copy(_image):
        pytest.fail("oversized target was copied before the pixel-budget check")

    monkeypatch.setattr(bridge, "_edge_pad_even", no_full_copy)
    with pytest.raises(ValueError, match="auxiliary_image_too_large"):
        bridge._prepare_native_2x_inputs(source, baseline, work_dir)
    assert not work_dir.exists()


def test_png_header_inspection_reads_exif_orientation_without_full_decode(tmp_path, monkeypatch):
    from signprint_ai.v211_large_image_bridge import inspect_image

    source = tmp_path / "oriented-header-only.png"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (9, 8), (30, 40, 50)).save(source, exif=exif)
    original_load = PngImagePlugin.PngImageFile.load

    def reject_full_raster_decode(image, *args, **kwargs):
        if image.size == (9, 8):
            pytest.fail("PNG EXIF header inspection must not decode customer pixels")
        return original_load(image, *args, **kwargs)

    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", reject_full_raster_decode)
    size, mode, metadata = inspect_image(source, orient=True)
    assert size == (8, 9)
    assert mode == "RGB"
    assert "icc_profile" not in metadata


def test_small_and_large_seed_paths_reject_mismatched_icc_before_writing(tmp_path):
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    source = tmp_path / "source-srgb.png"
    baseline = tmp_path / "v2-lab.png"
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    lab = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    Image.new("RGB", (128, 96), (40, 80, 120)).save(source, icc_profile=srgb)
    Image.new("RGB", (256, 192), (40, 80, 120)).save(baseline, icc_profile=lab)

    large_work = tmp_path / "large-must-not-be-created"
    with pytest.raises(ValueError, match="ICC differs"):
        prepare_native_2x_inputs_streamed(source, baseline, large_work)
    assert not large_work.exists()

    small_work = tmp_path / "small-must-not-be-created"
    with pytest.raises(ValueError, match="ICC differs"):
        bridge._prepare_native_2x_inputs(source, baseline, small_work)
    assert not small_work.exists()


@pytest.mark.parametrize("source_has_icc,v2_has_icc", [(False, True), (True, False)])
def test_small_and_large_seed_paths_reject_one_sided_icc(tmp_path, source_has_icc, v2_has_icc):
    from signprint_ai import v211_four_engine_bridge as bridge
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-v2.png"
    source_options = {"icc_profile": srgb} if source_has_icc else {}
    v2_options = {"icc_profile": srgb} if v2_has_icc else {}
    Image.new("RGB", (128, 96), (35, 80, 125)).save(source, **source_options)
    Image.new("RGB", (256, 192), (35, 80, 125)).save(baseline, **v2_options)

    large_work = tmp_path / "large-one-sided-icc"
    with pytest.raises(ValueError, match="ICC differs"):
        prepare_native_2x_inputs_streamed(source, baseline, large_work)
    assert not large_work.exists()

    small_work = tmp_path / "small-one-sided-icc"
    with pytest.raises(ValueError, match="ICC differs"):
        bridge._prepare_native_2x_inputs(source, baseline, small_work)
    assert not small_work.exists()

def test_large_four_engine_seed_and_qa_crop_use_disk_backed_vips_without_full_pillow_decode(
    tmp_path, monkeypatch
):
    pytest.importorskip("pyvips")
    import shutil
    from signprint_ai.v211_large_image_bridge import (
        prepare_native_2x_inputs_streamed,
        save_cropped_png_streamed,
    )

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "large-source.png"
    baseline = tmp_path / "accepted-large-v2.png"
    Image.new("RGB", (3000, 1000), (220, 30, 40)).save(
        source, dpi=(300, 300), icc_profile=profile
    )
    Image.new("RGB", (6001, 4001), (255, 255, 255)).save(
        baseline, dpi=(300, 300), icc_profile=profile
    )
    before = baseline.read_bytes()
    original_load = PngImagePlugin.PngImageFile.load
    forbidden_sizes = {
        (3000, 1000), (6001, 4001), (6002, 4002),
    }

    def reject_full_customer_raster_decode(image, *args, **kwargs):
        if image.size in forbidden_sizes:
            raise AssertionError("large bridge must use libvips, not full Pillow raster decode")
        return original_load(image, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(
            PngImagePlugin.PngImageFile, "load", reject_full_customer_raster_decode
        )
        work = tmp_path / "large-work"
        seed, reference, target, padded, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work, resize_mode="fit"
            )
        )
        assert source_size == (3000, 1000)
        assert target == (6001, 4001)
        assert padded == (6002, 4002)
        with Image.open(seed) as seed_header, Image.open(reference) as reference_header:
            assert seed_header.size == (3001, 2001)
            assert reference_header.size == padded
            assert seed_header.info["icc_profile"] == profile
            assert reference_header.info["icc_profile"] == profile
            assert seed_header.info["dpi"][0] == pytest.approx(300, abs=0.1)
            assert reference_header.info["dpi"][1] == pytest.approx(300, abs=0.1)

        fused = work / "four_engine_fused_preview.png"
        shutil.copyfile(reference, fused)
        qa = tmp_path / "accepted-large-v2.V211-4AI-QA-streamed.png"
        save_cropped_png_streamed(
            fused, qa,
            target_size=target,
            padded_size=padded,
            mode="RGB",
            metadata=metadata,
        )
        with Image.open(qa) as qa_header:
            assert qa_header.size == target
            assert qa_header.info["icc_profile"] == profile
            assert qa_header.info["dpi"][0] == pytest.approx(300, abs=0.1)
        assert baseline.read_bytes() == before

@pytest.mark.parametrize(
    ("source_ext", "target_ext"),
    [(".jpg", ".png"), (".webp", ".png"), (".png", ".jpg")],
)
def test_large_bridge_streams_jpeg_webp_source_and_jpeg_v2_before_gpu(
    tmp_path, monkeypatch, source_ext, target_ext
):
    """JPEG/WebP source and JPEG V2 use disk-backed libvips intermediates."""
    pytest.importorskip("pyvips")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / ("large-source" + source_ext)
    baseline = tmp_path / ("accepted-v2" + target_ext)

    source_options = {"icc_profile": profile}
    if source_ext in (".jpg", ".jpeg"):
        source_options.update({"quality": 95, "dpi": (300, 300)})
    elif source_ext == ".webp":
        source_options.update({"lossless": True})
    else:
        source_options.update({"dpi": (300, 300)})
    Image.new("RGB", (128, 128), (40, 80, 120)).save(source, **source_options)

    target_options = {"icc_profile": profile, "dpi": (300, 300)}
    if target_ext in (".jpg", ".jpeg"):
        target_options["quality"] = 95
    Image.new("RGB", (256, 256), (40, 80, 120)).save(baseline, **target_options)
    before = baseline.read_bytes()

    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 1024)

    prepared = []
    original_prepare = bridge.prepare_native_2x_inputs_streamed

    def capture_prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        seed, reference, target, padded, source_size, metadata = result
        with Image.open(seed) as seed_image, Image.open(reference) as reference_image:
            prepared.append({
                "seed_size": seed_image.size,
                "reference_size": reference_image.size,
                "icc_profile": reference_image.info.get("icc_profile"),
                "dpi": reference_image.info.get("dpi"),
                "target": target,
                "padded": padded,
                "source_size": source_size,
                "metadata": metadata,
            })
        return result

    monkeypatch.setattr(bridge, "prepare_native_2x_inputs_streamed", capture_prepare)

    def stop_before_native(*_args, **_kwargs):
        raise bridge.GPUDeviceBindingError("synthetic test stop before native launch")

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", stop_before_native)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_binding_unverified"
    assert result["v2_output_preserved"] is True
    assert len(prepared) == 1
    assert prepared[0]["seed_size"] == (128, 128)
    assert prepared[0]["reference_size"] == (256, 256)
    assert prepared[0]["target"] == (256, 256)
    assert prepared[0]["padded"] == (256, 256)
    assert prepared[0]["source_size"] == (128, 128)
    assert prepared[0]["icc_profile"] == profile
    assert prepared[0]["dpi"][0] == pytest.approx(300, abs=0.1)
    assert baseline.read_bytes() == before
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


@pytest.mark.parametrize("bigtiff", [False, True])
@pytest.mark.parametrize(
    ("source_ext", "target_ext"),
    [(".tiff", ".tiff"), (".tiff", ".png"), (".png", ".tiff")],
)
def test_large_single_page_tiff_and_bigtiff_use_streamed_png_intermediates(
    tmp_path, monkeypatch, bigtiff, source_ext, target_ext
):
    """Single-page RGB TIFF/BigTIFF inputs are streamed to private PNG tiles."""
    pytest.importorskip("pyvips")
    tifffile = pytest.importorskip("tifffile")
    from tools import v211_four_engine_run

    source = tmp_path / ("source" + source_ext)
    baseline = tmp_path / ("accepted-v2" + target_ext)
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    def save_raster(path, size, colour):
        width, height = size
        if path.suffix.lower() == ".png":
            Image.new("RGB", size, colour).save(
                path, dpi=(300, 300), icc_profile=profile
            )
            return
        pixels = np.empty((height, width, 3), dtype=np.uint8)
        pixels[:] = colour
        tifffile.imwrite(
            path,
            pixels,
            bigtiff=bigtiff,
            photometric="rgb",
            resolution=(300, 300),
            resolutionunit="INCH",
            extratags=[(34675, "B", len(profile), profile, False)],
        )

    save_raster(source, (128, 128), (40, 80, 120))
    save_raster(baseline, (256, 256), (40, 80, 120))
    original_v2 = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 1024)

    def fake_run(src, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        assert real_engines is True
        assert Path(src).suffix.lower() == ".png"
        assert Path(v2_reference).suffix.lower() == ".png"
        with Image.open(src) as seed, Image.open(v2_reference) as reference:
            assert seed.size == (128, 128)
            assert reference.size == (256, 256)
            assert seed.info.get("icc_profile") == profile
            assert reference.info.get("icc_profile") == profile
            assert seed.info.get("dpi")[0] == pytest.approx(300, abs=0.1)
            assert reference.info.get("dpi")[1] == pytest.approx(300, abs=0.1)
            fused = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fused, format="PNG")
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {
                name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
            },
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "four_engine_fusion_preview_ready", result
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert baseline.read_bytes() == original_v2
    qa = Path(result["four_engine_fusion_output"])
    assert qa.is_file()
    assert ".V211-4AI-QA-" in qa.name
    with Image.open(qa) as preview:
        assert preview.size == (256, 256)
        assert preview.mode == "RGB"
        assert preview.info.get("icc_profile") == profile
        assert preview.info.get("dpi")[0] == pytest.approx(300, abs=0.1)



@pytest.mark.parametrize(
    ("source_ext", "target_ext"),
    [(".jpg", ".png"), (".webp", ".png"), (".png", ".jpg")],
)
def test_large_bridge_streams_real_over_18mp_rasters_without_pillow_decode(
    tmp_path, monkeypatch, source_ext, target_ext
):
    """Real >18 MP JPEG/WebP/PNG inputs use libvips, not full Pillow decoding."""
    pytest.importorskip("pyvips")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    size = (4501, 4001)  # 18,008,501 pixels: strictly above the bridge threshold.
    source = tmp_path / ("large-source" + source_ext)
    baseline = tmp_path / ("accepted-v2" + target_ext)

    source_options = {"icc_profile": profile}
    if source_ext in (".jpg", ".jpeg"):
        source_options.update({"quality": 95, "dpi": (300, 300)})
    elif source_ext == ".webp":
        source_options.update({"lossless": True})
    else:
        source_options.update({"dpi": (300, 300)})
    Image.new("RGB", size, (40, 80, 120)).save(source, **source_options)

    target_options = {"icc_profile": profile, "dpi": (300, 300)}
    if target_ext in (".jpg", ".jpeg"):
        target_options["quality"] = 95
    Image.new("RGB", size, (40, 80, 120)).save(baseline, **target_options)
    before = baseline.read_bytes()

    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )

    prepared = []
    original_prepare = bridge.prepare_native_2x_inputs_streamed

    def capture_prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        seed, reference, target, padded, source_size, metadata = result
        with Image.open(seed) as seed_image, Image.open(reference) as reference_image:
            prepared.append({
                "seed_size": seed_image.size,
                "reference_size": reference_image.size,
                "icc_profile": reference_image.info.get("icc_profile"),
                "dpi": reference_image.info.get("dpi"),
                "target": target,
                "padded": padded,
                "source_size": source_size,
                "metadata": metadata,
            })
        return result

    monkeypatch.setattr(bridge, "prepare_native_2x_inputs_streamed", capture_prepare)

    original_file_load = ImageFile.ImageFile.load
    original_png_load = PngImagePlugin.PngImageFile.load
    forbidden_sizes = {size, (size[0] + 1, size[1] + 1)}

    def reject_full_customer_raster_decode(image, *args, **kwargs):
        if image.size in forbidden_sizes:
            raise AssertionError(
                "over-18MP bridge inputs/reference must remain disk-backed in libvips"
            )
        return original_file_load(image, *args, **kwargs)

    def reject_full_png_raster_decode(image, *args, **kwargs):
        if image.size in forbidden_sizes:
            raise AssertionError(
                "over-18MP PNG source/reference must remain disk-backed in libvips"
            )
        return original_png_load(image, *args, **kwargs)

    monkeypatch.setattr(
        ImageFile.ImageFile, "load", reject_full_customer_raster_decode
    )
    monkeypatch.setattr(
        PngImagePlugin.PngImageFile, "load", reject_full_png_raster_decode
    )

    def stop_before_native(*_args, **_kwargs):
        raise bridge.GPUDeviceBindingError(
            "synthetic test stop before native launch"
        )

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", stop_before_native)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_binding_unverified"
    assert result["v2_output_preserved"] is True
    assert len(prepared) == 1
    assert prepared[0]["seed_size"] == (2251, 2001)
    assert prepared[0]["reference_size"] == (4502, 4002)
    assert prepared[0]["target"] == size
    assert prepared[0]["padded"] == (4502, 4002)
    assert prepared[0]["source_size"] == size
    assert prepared[0]["icc_profile"] == profile
    assert prepared[0]["dpi"][0] == pytest.approx(300, abs=0.1)
    assert prepared[0]["dpi"][1] == pytest.approx(300, abs=0.1)
    assert baseline.read_bytes() == before
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


@pytest.mark.parametrize("multi_page_role", ["source", "v2"])
def test_large_bridge_rejects_multipage_tiff_before_gpu_and_preserves_v2(
    tmp_path, monkeypatch, multi_page_role
):
    """A TIFF/BigTIFF container with multiple pages must never be truncated to page one."""
    tifffile = pytest.importorskip("tifffile")
    pixels = np.zeros((32, 32, 3), dtype=np.uint8)
    multi_page = tmp_path / "multi-page-bigtiff.tiff"
    with tifffile.TiffWriter(multi_page, bigtiff=True) as writer:
        writer.write(pixels, photometric="rgb")
        writer.write(pixels, photometric="rgb")
    valid = tmp_path / "valid.png"
    Image.new("RGB", (128, 128), (40, 80, 120)).save(valid)
    source, baseline = (
        (multi_page, valid) if multi_page_role == "source"
        else (valid, multi_page)
    )
    original_v2 = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 1024)

    def forbidden(*_args, **_kwargs):
        pytest.fail("multipage TIFF must be rejected before GPU binding")

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", forbidden)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "error"
    assert result["error_type"] == "ValueError"
    assert result["v2_output_preserved"] is True
    assert baseline.read_bytes() == original_v2
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


@pytest.mark.parametrize("target_scale", [2, 3, 4, 8])
def test_large_bridge_routes_2x_3x_4x_and_8x_png_through_streamed_seed_and_tiled_runner(
    tmp_path, monkeypatch, target_scale
):
    """Exercise custom large output scales through one native 2x tiled pass."""
    pytest.importorskip("pyvips")
    import tools.v211_four_engine_run as runner
    import tools.v211_four_engine_fusion as fusion
    from tools.v211_four_engine_coordinator import ENGINES
    from tools.v211_four_engine_subprocess import EngineCommand

    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-v2.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source_image = Image.new("RGB", (128, 128), (40, 80, 120))
    source_image.paste((140, 160, 180), (64, 0, 128, 128))
    source_image.save(source, dpi=(300, 300), icc_profile=profile)
    target_size = (128 * target_scale, 128 * target_scale)
    v2_image = source_image.resize(target_size, resample=Image.Resampling.NEAREST)
    v2_image.save(baseline, dpi=(300, 300), icc_profile=profile)
    original_v2 = baseline.read_bytes()

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(manifest))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)

    # Force the exact same streamed code branches used above 18 MP without
    # allocating a 24 MP fixture in this orchestration test.
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 1024)
    monkeypatch.setattr(runner, "MAX_FOUR_ENGINE_PIXELS", 1024)
    monkeypatch.setattr(fusion, "MAX_RGBA_VALIDATION_PIXELS", 1024)

    def bind_manifest(_manifest, work_dir):
        bound = Path(work_dir) / "manifest.runtime-bound.json"
        bound.write_text("{}", encoding="utf-8")
        return bound, {
            "binding_configured": True,
            "runtime_device_use_verified": False,
        }

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", bind_manifest)
    monkeypatch.setattr(
        runner,
        "load_real_engine_manifest",
        lambda _path: {
            name: EngineCommand(
                (f"fake-{name}", "--input", "{input}", "--output", "{output}")
            )
            for name in ENGINES
        },
    )

    def processor(name):
        # Anime4K keeps its weaker test edge delta and low production weight.
        # For the 3x/4x Lanczos-seed cases, tune only the synthetic Real-ESRGAN
        # delta so the conditional Anime4K term crosses final 8-bit rounding
        # in the leave-one-engine-out attribution check.
        amount = {
            "real_esrgan": 8 if target_scale in (3, 4) else 9,
            "waifu2x": 7,
            "real_cugan": 8,
            "anime4k": 5,
        }[name]

        def run_tile(input_path, output_path):
            with Image.open(input_path) as tile:
                metadata = {
                    key: tile.info[key]
                    for key in ("icc_profile", "dpi")
                    if key in tile.info
                }
                enlarged = tile.resize(
                    (tile.width * 2, tile.height * 2),
                    resample=Image.Resampling.NEAREST,
                )
                pixels = np.asarray(enlarged, dtype=np.int16).copy()
                # Place synthetic engine detail at the rescaled source edge,
                # not at a fixed output column; half-target seeds vary by scale.
                boundary = enlarged.width // 2
                pixels[:, boundary - 1, :] = np.clip(
                    pixels[:, boundary - 1, :] - amount, 0, 255
                )
                pixels[:, boundary, :] = np.clip(
                    pixels[:, boundary, :] + amount, 0, 255
                )
                Image.fromarray(pixels.astype(np.uint8), "RGB").save(
                    output_path, format="PNG", **metadata
                )
        return run_tile

    processors = {name: processor(name) for name in ENGINES}
    def make_verified_processors(
        _commands,
        cancel_check=None,
        pre_launch_check=None,
        execution_records=None,
        runtime_device_probe=None,
        runtime_vram_guard=False,
    ):
        # The production runner must require both the per-process GPU probe
        # and the live whole-device VRAM reserve guard before four-engine QA.
        assert runtime_vram_guard is True
        wrapped = {}
        for engine_name, processor in processors.items():
            def run_verified(source_path, output_path, _name=engine_name, _processor=processor):
                _processor(source_path, output_path)
                if execution_records is not None:
                    record = execution_records.setdefault(_name, {})
                    process_count = int(record.get("runtime_device_process_count", 0)) + 1
                    record.update({
                        "runtime_device_process_count": process_count,
                        "runtime_device_verified_process_count": process_count,
                        "runtime_device_sample_count": process_count,
                        "runtime_device_all_processes_verified": True,
                        "runtime_device_use_verified": True,
                        # Synthetic, test-only NVML evidence. Runtime enforcement
                        # itself is exercised by test_v211_per_process_vram_guard.
                        "runtime_vram_guard_enabled": True,
                        "runtime_vram_guard_status": "within_budget",
                        "runtime_vram_sample_count": process_count,
                        "runtime_vram_peak_used_mib": 2048.0,
                        "runtime_vram_min_free_mib": 4096.0,
                        "runtime_vram_reserve_mib": 512,
                    })
            wrapped[engine_name] = run_verified
        return wrapped

    monkeypatch.setattr(runner, "make_processors", make_verified_processors)

    streamed_prepare_calls = []
    original_prepare = bridge.prepare_native_2x_inputs_streamed

    def track_streamed_prepare(*args, **kwargs):
        streamed_prepare_calls.append(Path(args[0]))
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(
        bridge, "prepare_native_2x_inputs_streamed", track_streamed_prepare
    )

    tiled_runner_calls = []
    original_tiled_runner = runner.run_tiled_candidates

    def track_tiled_runner(*args, **kwargs):
        tiled_runner_calls.append(Path(args[0]))
        return original_tiled_runner(*args, **kwargs)

    monkeypatch.setattr(runner, "run_tiled_candidates", track_tiled_runner)

    result = bridge.maybe_run_four_engine_assist(
        source, baseline, resize_mode="stretch"
    )

    assert result.get("status") != "error", result
    assert streamed_prepare_calls == [source]
    assert tiled_runner_calls, "large bridge must route through disk-backed native tiles"
    assert result["completed_engine_count"] == 4
    assert result["fusion_implemented"] is True
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False

    if target_scale == 8:
        # The 8x source is first resampled to a 4x half-target seed. In this
        # high-contrast synthetic fixture, the conditional Anime4K detail
        # exceeds its conservative agreement gate, so fail closed: keep all
        # four candidate runs as diagnostic evidence but publish no fused QA.
        assert result["status"] == "four_engine_fusion_contribution_incomplete"
        assert result["all_four_engine_pixels_contributed"] is False
        assert result["engine_pixel_effect_verified"]["anime4k"] is False
        assert all(
            result["engine_pixel_effect_verified"][name]
            for name in ("real_esrgan", "waifu2x", "real_cugan")
        )
        assert result["four_engine_fusion_output"] is None
        assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))
    else:
        assert result["all_four_engine_pixels_contributed"] is True, result
        assert all(result["engine_pixel_effect_verified"].values())
        qa = Path(result["four_engine_fusion_output"])
        assert qa.is_file()
        assert ".V211-4AI-QA-" in qa.name
        with Image.open(qa) as preview:
            assert preview.size == target_size
            assert preview.mode == "RGB"
            assert preview.info.get("icc_profile") == profile
            assert preview.info.get("dpi")[0] == pytest.approx(300, abs=0.1)
    assert baseline.read_bytes() == original_v2


def test_four_engine_qa_is_withheld_without_runtime_adapter_proof(
    tmp_path, monkeypatch
):
    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run

    def fake_run(_src, output_dir, _manifest, size, **_kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        fused = output_dir / "four_engine_fused_preview.png"
        Image.new("RGBA", size, (210, 20, 40, 120)).save(fused)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": False,
            "per_engine_runtime_device_use_verified": {
                "real_esrgan": True,
                "waifu2x": True,
                "real_cugan": True,
                "anime4k": False,
            },
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_runtime_unverified"
    assert result["runtime_device_use_verified"] is False
    assert result["per_engine_runtime_device_use_verified"]["anime4k"] is False
    assert result["four_engine_fusion_output"] is None
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))
    assert baseline.read_bytes() == before

def test_large_24mp_bigtiff_seed_and_qa_crop_use_disk_backed_vips_without_full_pillow_decode(
    tmp_path, monkeypatch
):
    """A real >18 MP BigTIFF uses libvips regions and keeps the accepted V2 file intact."""
    pytest.importorskip("pyvips")
    tifffile = pytest.importorskip("tifffile")
    import hashlib
    import shutil
    from PIL import TiffImagePlugin
    from signprint_ai.v211_large_image_bridge import (
        prepare_native_2x_inputs_streamed,
        save_cropped_png_streamed,
    )

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "large-source-bigtiff.tif"
    baseline = tmp_path / "accepted-large-v2-bigtiff.tif"

    def write_bigtiff(path, size, colour):
        width, height = size
        pixels = np.empty((height, width, 3), dtype=np.uint8)
        pixels[:] = colour
        tifffile.imwrite(
            path,
            pixels,
            bigtiff=True,
            photometric="rgb",
            resolution=(300, 300),
            resolutionunit="INCH",
            extratags=[(34675, "B", len(profile), profile, False)],
        )

    write_bigtiff(source, (3000, 1000), (220, 30, 40))
    write_bigtiff(baseline, (6001, 4001), (255, 255, 255))

    def file_sha256(path):
        with Path(path).open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    before_sha = file_sha256(baseline)
    original_load = TiffImagePlugin.TiffImageFile.load
    forbidden_sizes = {(3000, 1000), (6001, 4001), (6002, 4002)}

    def reject_full_customer_raster_decode(image, *args, **kwargs):
        if image.size in forbidden_sizes:
            raise AssertionError("large BigTIFF must use libvips, not full Pillow raster decode")
        return original_load(image, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(
            TiffImagePlugin.TiffImageFile, "load", reject_full_customer_raster_decode
        )
        work = tmp_path / "large-bigtiff-work"
        seed, reference, target, padded, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work, resize_mode="fit"
            )
        )
        assert source_size == (3000, 1000)
        assert target == (6001, 4001)
        assert padded == (6002, 4002)
        with Image.open(seed) as seed_header, Image.open(reference) as reference_header:
            assert seed_header.size == (3001, 2001)
            assert reference_header.size == padded
            assert seed_header.info["icc_profile"] == profile
            assert reference_header.info["icc_profile"] == profile
            assert seed_header.info["dpi"][0] == pytest.approx(300, abs=0.1)
            assert reference_header.info["dpi"][1] == pytest.approx(300, abs=0.1)

        fused = work / "four_engine_fused_preview.png"
        shutil.copyfile(reference, fused)
        qa = tmp_path / "accepted-large-v2-bigtiff.V211-4AI-QA-streamed.png"
        save_cropped_png_streamed(
            fused,
            qa,
            target_size=target,
            padded_size=padded,
            mode="RGB",
            metadata=metadata,
        )
        with Image.open(qa) as qa_header:
            assert qa_header.size == target
            assert qa_header.info["icc_profile"] == profile
            assert qa_header.info["dpi"][0] == pytest.approx(300, abs=0.1)
    assert file_sha256(baseline) == before_sha


@pytest.mark.parametrize(
    ("target_size", "expected_scale"),
    [
        ((256, 256), (4.0, 4.0)),
        ((512, 512), (8.0, 8.0)),
        ((256, 192), (4.0, 3.0)),
        ((257, 193), (4.0156, 3.0156)),
    ],
)
def test_large_disk_backed_bridge_supports_custom_print_scales_without_extra_native_pass(
    tmp_path, monkeypatch, target_size, expected_scale
):
    """Large jobs resize to a half-target seed, then make one native 2x pass."""
    pytest.importorskip("pyvips")
    source = tmp_path / "large-source.png"
    baseline = tmp_path / "accepted-v2.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (64, 64), (20, 30, 40)).save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    Image.new("RGB", target_size, (30, 40, 50)).save(
        baseline, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    before = baseline.read_bytes()

    # Force the disk-backed branch with small synthetic rasters. The production
    # threshold remains 18 MP; the smaller threshold keeps this regression fast.
    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 4096)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)

    from tools import v211_four_engine_run
    observed = []

    def fake_run(seed_path, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(seed_path) as seed, Image.open(v2_reference) as reference:
            observed.append((seed.size, reference.size, tuple(size), real_engines))
            fused = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fused, format="PNG")
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {
                name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
            },
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    padded = (target_size[0] + target_size[0] % 2, target_size[1] + target_size[1] % 2)
    expected_seed = (padded[0] // 2, padded[1] // 2)
    assert observed == [(expected_seed, padded, padded, True)]
    assert result["status"] == "four_engine_fusion_preview_ready"
    assert result["four_engine_fusion_details"]["native_engine_scale"] == 2
    assert result["four_engine_fusion_details"]["scale_policy"] == "native_2x_on_half_target_seed"
    assert result["four_engine_fusion_details"]["engine_input_size"] == list(expected_seed)
    assert result["four_engine_fusion_details"]["requested_output_size"] == list(target_size)
    assert result["four_engine_fusion_details"]["requested_scale_from_source"] == list(expected_scale)
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert baseline.read_bytes() == before

    preview = Path(result["four_engine_fusion_output"])
    with Image.open(preview) as image:
        assert image.size == target_size
        assert image.mode == "RGB"
        assert image.info.get("icc_profile") == profile
        assert image.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)


def test_large_bigtiff_end_to_end_tiled_fusion_fails_closed_without_real_adapter_evidence(
    tmp_path, monkeypatch
):
    """Exercise >18 MP TIFF -> streamed PNG -> four tiled processors -> fusion.

    The processors are deterministic synthetic CPU fixtures, not native AI
    inference. Even after all four contribute to a valid private fusion image,
    the application must refuse to publish a QA sidecar without live per-PID
    adapter evidence and must leave the accepted BigTIFF byte-identical.
    """
    pytest.importorskip("pyvips")
    tifffile = pytest.importorskip("tifffile")

    from tools.v211_four_engine_coordinator import ENGINES
    from tools.v211_four_engine_fusion import fuse_four_engine_details
    from tools.v211_four_engine_tiled_inference import run_tiled_candidates
    from tools import v211_four_engine_run

    width = 2122
    height = 2122
    target_size = (width * 2, height * 2)
    assert target_size[0] * target_size[1] > 18_000_000

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    columns = np.arange(width, dtype=np.uint32)
    stripe = np.where((columns // 32) % 2 == 0, 119, 137).astype(np.uint8)
    row = np.repeat(stripe[:, None], 3, axis=1)
    source_pixels = np.broadcast_to(row[None, :, :], (height, width, 3)).copy()
    v2_pixels = np.repeat(np.repeat(source_pixels, 2, axis=0), 2, axis=1)

    source = tmp_path / "synthetic-source.tiff"
    baseline = tmp_path / "accepted-v2-bigtiff.tiff"

    def write_tiff(path, pixels, *, bigtiff):
        tifffile.imwrite(
            path,
            pixels,
            bigtiff=bigtiff,
            photometric="rgb",
            resolution=(300, 300),
            resolutionunit="INCH",
            extratags=[(34675, "B", len(profile), profile, False)],
        )

    write_tiff(source, source_pixels, bigtiff=False)
    write_tiff(baseline, v2_pixels, bigtiff=True)
    del source_pixels, v2_pixels

    import hashlib

    def digest(path):
        value = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(block)
        return value.hexdigest()

    accepted_v2_sha = digest(baseline)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "synthetic-manifest.json")
    )
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)

    observed = {}

    def synthetic_contrast_processor(source_tile, destination):
        with Image.open(source_tile) as image:
            pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
            enhanced = np.clip(128 + (pixels - 128) * 2, 0, 255).astype(np.uint8)
            output = Image.fromarray(enhanced, "RGB").resize(
                (image.width * 2, image.height * 2),
                resample=Image.Resampling.NEAREST,
            )
            options = {}
            if image.info.get("icc_profile") is not None:
                options["icc_profile"] = image.info["icc_profile"]
            if image.info.get("dpi") is not None:
                options["dpi"] = image.info["dpi"]
            output.save(destination, format="PNG", **options)
            output.close()

    def _synthetic_run_impl(
        seed_path, output_dir, manifest, size, *, real_engines,
        v2_reference, **kwargs
    ):
        assert real_engines is True
        assert tuple(size) == target_size
        with Image.open(seed_path) as seed:
            assert seed.size == (width, height)
            assert seed.mode == "RGB"
            assert seed.info.get("icc_profile") == profile
            assert seed.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)
        with Image.open(v2_reference) as reference:
            assert reference.size == target_size
            assert reference.mode == "RGB"
            assert reference.info.get("icc_profile") == profile
            assert reference.info.get("dpi", (0, 0))[1] == pytest.approx(300, abs=0.1)

        candidate_dir = Path(output_dir) / "synthetic-tiled-candidates"
        tiled = run_tiled_candidates(
            Path(seed_path),
            Path(v2_reference),
            candidate_dir,
            tuple(size),
            {name: synthetic_contrast_processor for name in ENGINES},
            tile_size=1024,
            overlap=32,
        )
        assert tiled["ready_for_fusion_research"] is True
        assert tiled["native_tiled_inference"]["all_four_engines_completed"] is True
        for name in ENGINES:
            engine = tiled["native_tiled_inference"]["engine_results"][name]
            assert engine["status"] == "stitched"
            assert engine["tile_count"] == 9
            assert engine["seam_count"] == 12
            assert engine["seam_validation"] == "passed"

        candidates = {item.engine: item.path for item in tiled["candidates"]}
        fused_path = Path(output_dir) / "four_engine_fused_preview.png"
        fusion = fuse_four_engine_details(
            Path(seed_path), Path(v2_reference), candidates, fused_path
        )
        assert fusion["fusion_implemented"] is True
        assert fusion["all_four_engine_candidates_consumed"] is True
        assert fusion["all_four_engine_pixels_contributed"] is True, fusion
        assert all(fusion["engine_pixel_effect_verified"].values())
        with Image.open(fused_path) as preview:
            assert preview.size == target_size
            assert preview.mode == "RGB"
            assert preview.info.get("icc_profile") == profile
            assert preview.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)

        observed["tile_reports"] = tiled["native_tiled_inference"]["engine_results"]
        observed["fusion"] = fusion
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            # Synthetic processors deliberately provide no GPU/adapter proof.
            "runtime_device_use_verified": False,
            "per_engine_runtime_device_use_verified": {
                name: False for name in ENGINES
            },
            "four_engine_fusion": fusion,
        }

    def synthetic_run(*args, **kwargs):
        try:
            return _synthetic_run_impl(*args, **kwargs)
        except Exception as exc:
            observed["synthetic_pipeline_error"] = type(exc).__name__ + ": " + str(exc)
            raise

    monkeypatch.setattr(v211_four_engine_run, "run", synthetic_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert "synthetic_pipeline_error" not in observed, observed.get("synthetic_pipeline_error")
    assert len(observed["tile_reports"]) == 4
    assert observed["fusion"]["all_four_engine_pixels_contributed"] is True
    assert result["status"] == "gpu_runtime_unverified"
    assert result["four_engine_fusion_output"] is None
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert digest(baseline) == accepted_v2_sha
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))

@pytest.mark.parametrize(
    ("target_size", "expected_seed"),
    [
        ((256, 256), (128, 128)),  # 4x source-to-print
        ((512, 512), (256, 256)),  # 8x source-to-print, still one native 2x pass
        ((256, 192), (128, 96)),   # anisotropic 4x by 3x
    ],
)
def test_large_streamed_bridge_keeps_native_2x_geometry_for_custom_print_scales(
    tmp_path, monkeypatch, target_size, expected_seed
):
    """Large jobs use a half-target seed; this is a bridge contract test, not GPU evidence."""
    import shutil

    source = tmp_path / "large-contract-source.png"
    baseline = tmp_path / "large-contract-v2.png"
    Image.new("RGB", (64, 64), (40, 80, 120)).save(source, dpi=(300, 300))
    Image.new("RGB", target_size, (90, 100, 110)).save(baseline, dpi=(300, 300))
    before = baseline.read_bytes()

    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 1024)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json")
    )
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)

    def fake_prepare(source_path, v2_path, work_dir, *, resize_mode,
                     cancel_check=None, progress_callback=None):
        work_dir.mkdir(parents=True, exist_ok=True)
        padded = (
            target_size[0] + target_size[0] % 2,
            target_size[1] + target_size[1] % 2,
        )
        seed_size = (padded[0] // 2, padded[1] // 2)
        seed = work_dir / "native_2x_seed.png"
        reference = work_dir / "v2_reference_native_2x.png"
        with Image.open(source_path) as image:
            image.resize(seed_size, Image.Resampling.LANCZOS).save(
                seed, format="PNG", dpi=image.info.get("dpi")
            )
        with Image.open(v2_path) as image:
            metadata = {
                key: image.info[key]
                for key in ("icc_profile", "dpi")
                if key in image.info
            }
            image.save(reference, format="PNG", **metadata)
        return seed, reference, target_size, padded, (64, 64), metadata

    def fake_run(seed, output_dir, manifest, size, *, real_engines,
                 v2_reference, **kwargs):
        with Image.open(seed) as seed_image, Image.open(v2_reference) as v2_image:
            assert seed_image.size == expected_seed
            assert v2_image.size == tuple(size)
            assert tuple(size) == (
                target_size[0] + target_size[0] % 2,
                target_size[1] + target_size[1] % 2,
            )
            fused = Path(output_dir) / "four_engine_fused_preview.png"
            metadata = {
                key: v2_image.info[key]
                for key in ("icc_profile", "dpi")
                if key in v2_image.info
            }
            v2_image.save(fused, format="PNG", **metadata)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {
                name: True
                for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
            },
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }

    def fake_crop(candidate, destination, *, target_size, padded_size,
                  mode, metadata, cancel_check=None):
        with Image.open(candidate) as image:
            assert image.size == padded_size
            assert image.mode == mode
            image.crop((0, 0, target_size[0], target_size[1])).save(
                destination, format="PNG", **metadata
            )

    from tools import v211_four_engine_run
    monkeypatch.setattr(bridge, "prepare_native_2x_inputs_streamed", fake_prepare)
    monkeypatch.setattr(bridge, "_save_cropped_png", fake_crop)
    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)

    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "four_engine_fusion_preview_ready"
    assert result["quality_certified"] is False
    assert result["v2_output_preserved"] is True
    assert result["four_engine_fusion_details"]["native_engine_scale"] == 2
    assert result["four_engine_fusion_details"]["scale_policy"] == "native_2x_on_half_target_seed"
    assert result["four_engine_fusion_details"]["engine_input_size"] == list(expected_seed)
    assert result["four_engine_fusion_details"]["requested_output_size"] == list(target_size)
    assert result["four_engine_fusion_details"]["requested_scale_from_source"] == [
        round(target_size[0] / 64, 4), round(target_size[1] / 64, 4)
    ]
    assert baseline.read_bytes() == before
    preview = Path(result["four_engine_fusion_output"])
    assert preview.is_file() and ".V211-4AI-QA-" in preview.name
    with Image.open(preview) as image:
        assert image.size == target_size
        assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)

@pytest.mark.parametrize("extension", [".jpg", ".webp"])
def test_jpeg_webp_exif_orientation_is_header_only_without_full_decode(
    tmp_path, monkeypatch, extension
):
    """Large JPEG/WebP orientation is read from container metadata, not pixels."""
    from signprint_ai.v211_large_image_bridge import inspect_image

    source = tmp_path / ("oriented" + extension)
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise when applying EXIF orientation.
    image = Image.new("RGB", (64, 32), (40, 80, 120))
    try:
        if extension == ".jpg":
            image.save(source, format="JPEG", quality=95, exif=exif.tobytes())
        else:
            image.save(source, format="WEBP", lossless=True, exif=exif.tobytes())
    except (KeyError, OSError) as exc:
        pytest.skip(f"this Pillow build does not support {extension}: {exc}")
    finally:
        image.close()

    # Confirm the test file really contains the orientation tag before
    # forbidding every full raster decode through Pillow.
    with Image.open(source) as check:
        assert check.getexif().get(274) == 6

    def reject_pixel_decode(_image, *args, **kwargs):
        raise AssertionError("large JPEG/WebP EXIF preflight must not decode pixels")

    monkeypatch.setattr(ImageFile.ImageFile, "load", reject_pixel_decode)
    size, mode, _metadata = inspect_image(source, orient=True)
    assert size == (32, 64)
    assert mode == "RGB"
    raw_size, raw_mode, _raw_metadata = inspect_image(source, orient=False)
    assert raw_size == (64, 32)
    assert raw_mode == "RGB"



def test_real_four_engine_preview_writes_path_free_evidence_sidecar(tmp_path, monkeypatch):
    import hashlib
    import json

    source, baseline = _images(tmp_path)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run

    def sha(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def fake_run(seed, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        output = Path(output_dir) / "four_engine_fused_preview.png"
        with Image.open(v2_reference) as reference:
            reference.save(output, format="PNG")
        candidate_hashes = {
            name: hashlib.sha256(name.encode("ascii")).hexdigest()
            for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
        }
        return {
            "ready_for_fusion_research": True,
            "real_engine_manifest_preflight_passed": True,
            "source_sha256": sha(seed),
            "v2_reference_sha256": sha(v2_reference),
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {
                name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
            },
            "completed_engine_count": 4,
            "completed_engine_names": ["real_esrgan", "waifu2x", "real_cugan", "anime4k"],
            "candidate_sha256": candidate_hashes,
            "fusion_implemented": True,
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_candidates_consumed": True,
                "all_four_engine_pixels_contributed": True,
                "engine_pixel_effect_verified": {
                    name: True for name in candidate_hashes
                },
                "engine_pixel_effect_pixels": {
                    name: 12 for name in candidate_hashes
                },
                "output": str(output),
                "output_sha256": sha(output),
            },
            "failures": {},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "four_engine_fusion_preview_ready"
    assert result["quality_certified"] is False
    assert result["v2_output_preserved"] is True
    assert result["qa_evidence_report"]
    evidence_path = Path(result["qa_evidence_report"])
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    qa_path = Path(result["four_engine_fusion_output"])
    assert evidence["source_sha256"] == sha(source)
    assert evidence["v2_reference_sha256"] == sha(baseline)
    assert evidence["qa_image_sha256"] == sha(qa_path)
    assert evidence["runtime_device_use_verified"] is True
    assert evidence["all_four_engine_pixels_contributed"] is True
    assert evidence["quality_certified"] is False
    assert str(tmp_path) not in json.dumps(evidence)
    assert baseline.read_bytes() == before


def test_large_24mp_four_x_print_path_uses_one_native_two_x_tiled_pass_and_fails_closed_without_gpu_evidence(
    tmp_path, monkeypatch
):
    """Exercise the real disk-backed 24 MP seed/tile/fusion path with CPU fixtures.

    This validates geometry, ICC/DPI, tile seams, pixel contribution and V2
    preservation only. A separate bridge invocation verifies that the same
    large-job path with unverified physical GPU evidence publishes no QA file.
    """
    pytest.importorskip("pyvips")
    tifffile = pytest.importorskip("tifffile")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    from tools.v211_four_engine_coordinator import ENGINES
    from tools.v211_four_engine_fusion import fuse_four_engine_details
    from tools.v211_four_engine_tiled_inference import run_tiled_candidates
    from tools import v211_four_engine_run

    source_width, source_height = 1500, 1000
    source_size = (source_width, source_height)
    target_size = (source_width * 4, source_height * 4)
    assert target_size[0] * target_size[1] == 24_000_000

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    # Use a single high-contrast contour like the existing 4x scale contract.
    # This gives the deliberately low-weight Anime4K term a measurable
    # counterfactual effect after final 8-bit rounding, without changing fusion.
    source_pixels = np.empty((source_height, source_width, 3), dtype=np.uint8)
    source_pixels[:, :source_width // 2] = (40, 80, 120)
    source_pixels[:, source_width // 2:] = (140, 160, 180)
    # The accepted V2 raster is 4x. Native engines still receive one 2x pass
    # from a seed that is exactly half the accepted V2 target dimensions.
    v2_pixels = np.repeat(np.repeat(source_pixels, 4, axis=0), 4, axis=1)

    source = tmp_path / "synthetic-4x-source.tiff"
    baseline = tmp_path / "accepted-v2-24mp-bigtiff.tiff"

    def write_tiff(path, pixels, *, bigtiff):
        tifffile.imwrite(
            path,
            pixels,
            bigtiff=bigtiff,
            photometric="rgb",
            resolution=(300, 300),
            resolutionunit="INCH",
            extratags=[(34675, "B", len(profile), profile, False)],
        )

    write_tiff(source, source_pixels, bigtiff=False)
    write_tiff(baseline, v2_pixels, bigtiff=True)
    del source_pixels, v2_pixels

    import hashlib

    def digest(path):
        value = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(block)
        return value.hexdigest()

    accepted_v2_sha = digest(baseline)
    work_dir = tmp_path / "large-4x-work"
    (
        seed_path, reference_path, prepared_target_size, padded_size,
        prepared_source_size, metadata,
    ) = prepare_native_2x_inputs_streamed(
        source, baseline, work_dir, resize_mode="stretch"
    )

    assert prepared_source_size == source_size
    assert prepared_target_size == target_size
    assert padded_size == target_size
    with Image.open(seed_path) as seed:
        assert seed.size == (source_width * 2, source_height * 2)
        assert seed.mode == "RGB"
        assert seed.info.get("icc_profile") == profile
        assert seed.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)
    with Image.open(reference_path) as reference:
        assert reference.size == target_size
        assert reference.mode == "RGB"
        assert reference.info.get("icc_profile") == profile
        assert reference.info.get("dpi", (0, 0))[1] == pytest.approx(300, abs=0.1)

    def synthetic_detail_processor(engine_name):
        # Keep the same per-engine edge deltas used by the passing 4x scale
        # contract. The weaker Anime4K weight needs this controlled positive
        # edge fixture; identical contrast outputs for all engines can be
        # consumed yet quantize to zero Anime4K pixel contribution at 4x.
        amount = {
            "real_esrgan": 8,
            "waifu2x": 7,
            "real_cugan": 8,
            "anime4k": 5,
        }[engine_name]

        def process(source_tile, destination):
            with Image.open(source_tile) as image:
                source_rgb = image.convert("RGB")
                gradients = np.abs(
                    np.diff(np.asarray(source_rgb, dtype=np.int16), axis=1)
                ).mean(axis=(0, 2))
                enlarged = source_rgb.resize(
                    (image.width * 2, image.height * 2),
                    resample=Image.Resampling.NEAREST,
                )
                pixels = np.asarray(enlarged, dtype=np.int16).copy()
                if gradients.size and float(gradients.max()) > 0:
                    # Find the actual contour in this tile rather than assuming
                    # it is at the tile centre; overlap tiles may start at
                    # different global coordinates.
                    boundary = (int(np.argmax(gradients)) + 1) * 2
                    if 0 < boundary < pixels.shape[1]:
                        pixels[:, boundary - 1, :] = np.clip(
                            pixels[:, boundary - 1, :] - amount, 0, 255
                        )
                        pixels[:, boundary, :] = np.clip(
                            pixels[:, boundary, :] + amount, 0, 255
                        )
                options = {
                    key: image.info[key]
                    for key in ("icc_profile", "dpi")
                    if key in image.info
                }
                Image.fromarray(pixels.astype(np.uint8), "RGB").save(
                    destination, format="PNG", **options
                )
                enlarged.close()
                source_rgb.close()

        return process

    candidate_dir = work_dir / "synthetic-4x-tiled-candidates"
    tiled = run_tiled_candidates(
        seed_path,
        reference_path,
        candidate_dir,
        target_size,
        {name: synthetic_detail_processor(name) for name in ENGINES},
        tile_size=1024,
        overlap=32,
    )
    assert tiled["ready_for_fusion_research"] is True, tiled["failures"]
    assert tiled["native_tiled_inference"]["all_four_engines_completed"] is True
    for name in ENGINES:
        engine = tiled["native_tiled_inference"]["engine_results"][name]
        assert engine["status"] == "stitched", engine
        assert engine["tile_count"] == 6, engine
        assert engine["seam_count"] == 7, engine
        assert engine["seam_validation"] == "passed", engine

    candidates = {item.engine: item.path for item in tiled["candidates"]}
    fused_path = work_dir / "four_engine_fused_preview.png"
    fusion = fuse_four_engine_details(
        seed_path, reference_path, candidates, fused_path
    )
    assert fusion["fusion_implemented"] is True
    assert fusion["all_four_engine_candidates_consumed"] is True
    assert fusion["all_four_engine_pixels_contributed"] is True, fusion
    assert all(fusion["engine_pixel_effect_verified"].values())
    with Image.open(fused_path) as preview:
        assert preview.size == target_size
        assert preview.mode == "RGB"
        assert preview.info.get("icc_profile") == profile
        assert preview.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)

    # Exercise the bridge's fail-closed publication gate independently of the
    # CPU fixture. The actual disk-backed seed/tile/fusion above has completed,
    # but a missing physical-adapter proof must suppress the QA sidecar.
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    manifest = tmp_path / "synthetic-manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(manifest))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    monkeypatch.setattr(
        bridge,
        "prepare_native_2x_inputs_streamed",
        lambda *_args, **_kwargs: (
            seed_path, reference_path, target_size, padded_size, source_size, metadata
        ),
    )

    def unverified_run(
        _seed, _output_dir, _manifest, size, *, real_engines,
        v2_reference, **_kwargs
    ):
        assert real_engines is True
        assert tuple(size) == target_size
        assert Path(v2_reference) == reference_path
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "runtime_device_use_verified": False,
            "per_engine_runtime_device_use_verified": {
                name: False for name in ENGINES
            },
            "fusion_block_reason": "gpu_runtime_unverified",
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_candidates_consumed": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused_path),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", unverified_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_runtime_unverified", result
    assert result["completed_engine_count"] == 4
    assert result["four_engine_fusion_output"] is None
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert digest(baseline) == accepted_v2_sha
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))

def test_large_four_x_rgba_bridge_preserves_v2_alpha_and_fails_closed_without_gpu_evidence(
    tmp_path, monkeypatch
):
    """Force the streamed 4x bridge with RGBA and verify V2 alpha remains authoritative.

    The small fixture exercises the exact disk-backed preparation/tile/fusion
    branch without allocating a 24 MP test raster. Native processors are
    deterministic CPU fixtures; absent physical-GPU evidence must suppress the
    QA sidecar and leave the accepted V2 file byte-identical.
    """
    pytest.importorskip("pyvips")
    from tools.v211_four_engine_coordinator import ENGINES
    from tools.v211_four_engine_fusion import fuse_four_engine_details
    from tools.v211_four_engine_tiled_inference import run_tiled_candidates
    from tools import v211_four_engine_run

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source_pixels = np.zeros((64, 64, 4), dtype=np.uint8)
    yy, xx = np.indices((64, 64))
    source_pixels[..., 0] = (xx * 3 + 20).astype(np.uint8)
    source_pixels[..., 1] = (yy * 2 + 40).astype(np.uint8)
    source_pixels[..., 2] = ((xx + yy) * 2 + 60).astype(np.uint8)
    source_pixels[..., 3] = 255
    source_pixels[12:52, 12:52, 3] = 128
    source_pixels[24:40, 24:40, 3] = 0

    source = tmp_path / "large-branch-rgba-source.png"
    baseline = tmp_path / "accepted-v2-four-x-rgba.png"
    Image.fromarray(source_pixels, "RGBA").save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    with Image.open(source) as original:
        v2 = original.resize((256, 256), Image.Resampling.LANCZOS)
        v2.save(baseline, format="PNG", dpi=(300, 300), icc_profile=profile)
        expected_alpha = np.asarray(v2.getchannel("A")).copy()
        v2.close()

    source_before = source.read_bytes()
    baseline_before = baseline.read_bytes()
    manifest = tmp_path / "synthetic-manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(bridge, "_AUXILIARY_MAX_PIXELS", 4096)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(manifest))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    monkeypatch.setattr(
        bridge,
        "_prepare_runtime_bound_manifest",
        lambda _manifest, _work_dir: (manifest, {"configured": True}),
    )

    observed = {}

    def synthetic_run(seed_path, output_dir, _manifest, size, *, real_engines, v2_reference, **_kwargs):
        assert real_engines is True
        assert tuple(size) == (256, 256)
        with Image.open(seed_path) as seed, Image.open(v2_reference) as reference:
            assert seed.size == (128, 128)
            assert seed.mode == "RGBA"
            assert seed.info.get("icc_profile") == profile
            assert seed.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)
            assert reference.size == (256, 256)
            assert reference.mode == "RGBA"
            np.testing.assert_array_equal(
                np.asarray(reference.getchannel("A")), expected_alpha
            )

        def drop_alpha_processor(tile_source, destination):
            with Image.open(tile_source) as tile:
                rgb = tile.convert("RGB")
                output = rgb.resize(
                    (tile.width * 2, tile.height * 2),
                    resample=Image.Resampling.NEAREST,
                )
                options = {
                    key: tile.info[key]
                    for key in ("icc_profile", "dpi")
                    if key in tile.info
                }
                output.save(destination, format="PNG", **options)
                output.close()
                rgb.close()

        candidate_dir = Path(output_dir) / "rgba-four-x-candidates"
        tiled = run_tiled_candidates(
            Path(seed_path),
            Path(v2_reference),
            candidate_dir,
            tuple(size),
            {name: drop_alpha_processor for name in ENGINES},
            tile_size=64,
            overlap=8,
        )
        assert tiled["ready_for_fusion_research"] is True, tiled["failures"]
        candidates = {item.engine: item.path for item in tiled["candidates"]}
        for name in ENGINES:
            with Image.open(candidates[name]) as candidate:
                assert candidate.mode == "RGBA"
                np.testing.assert_array_equal(
                    np.asarray(candidate.getchannel("A")), expected_alpha
                )
                assert candidate.info.get("icc_profile") == profile
                assert candidate.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)

        fused_path = Path(output_dir) / "rgba-four-x-fused.png"
        fusion = fuse_four_engine_details(
            Path(seed_path), Path(v2_reference), candidates, fused_path
        )
        assert fusion["fusion_implemented"] is True
        with Image.open(fused_path) as fused:
            assert fused.mode == "RGBA"
            np.testing.assert_array_equal(
                np.asarray(fused.getchannel("A")), expected_alpha
            )
            assert fused.info.get("icc_profile") == profile
            assert fused.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=0.1)

        observed["engine_names"] = [item.engine for item in tiled["candidates"]]
        observed["alpha_preserved"] = True
        observed["fusion"] = fusion
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": len(ENGINES),
            "completed_engine_names": list(ENGINES),
            "runtime_device_use_verified": False,
            "per_engine_runtime_device_use_verified": {
                name: False for name in ENGINES
            },
            "fusion_block_reason": "gpu_runtime_unverified",
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_candidates_consumed": fusion["all_four_engine_candidates_consumed"],
                "all_four_engine_pixels_contributed": fusion["all_four_engine_pixels_contributed"],
                "output": str(fused_path),
                "output_sha256": "0" * 64,
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", synthetic_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert observed["engine_names"] == list(ENGINES)
    assert observed["alpha_preserved"] is True
    assert result["status"] == "gpu_runtime_unverified"
    assert result["completed_engine_count"] == 4
    assert result["four_engine_fusion_output"] is None
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False
    assert source.read_bytes() == source_before
    assert baseline.read_bytes() == baseline_before
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))
