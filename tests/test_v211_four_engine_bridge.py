"""The four-engine bridge must be opt-in and must never rewrite V2."""
from pathlib import Path

import pytest
from PIL import Image, ImageCms, PngImagePlugin

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

def test_large_bridge_routes_streamed_seed_to_tiled_runner_and_streamed_qa(
    tmp_path, monkeypatch
):
    """Exercise the complete large-job bridge route with small synthetic files.

    Pixel thresholds are lowered only in this test so it covers orchestration
    cheaply. Separate 24 MP regressions cover the actual disk-backed seed,
    native tile runner, and streamed QA crop implementations.
    """
    pytest.importorskip("pyvips")
    import tools.v211_four_engine_run as runner
    import tools.v211_four_engine_fusion as fusion
    from tools.v211_four_engine_coordinator import ENGINES

    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-v2.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (128, 128), (40, 80, 120)).save(
        source, dpi=(300, 300), icc_profile=profile
    )
    Image.new("RGB", (256, 256), (40, 80, 120)).save(
        baseline, dpi=(300, 300), icc_profile=profile
    )
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
        lambda _path: {name: object() for name in ENGINES},
    )

    def processor(_name):
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
                enlarged.save(output_path, format="PNG", **metadata)
        return run_tile

    processors = {name: processor(name) for name in ENGINES}
    monkeypatch.setattr(
        runner,
        "make_processors",
        lambda _commands, cancel_check=None, execution_records=None: processors,
    )

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

    assert streamed_prepare_calls == [source]
    assert tiled_runner_calls, "large bridge must route through disk-backed native tiles"
    assert result["completed_engine_count"] == 4
    assert result["fusion_implemented"] is True
    assert result["v2_output_preserved"] is True
    assert result["quality_certified"] is False

    qa = Path(result["four_engine_fusion_output"])
    assert qa.is_file()
    assert ".V211-4AI-QA-" in qa.name
    with Image.open(qa) as preview:
        assert preview.size == (256, 256)
        assert preview.mode == "RGB"
        assert preview.info.get("icc_profile") == profile
        assert preview.info.get("dpi")[0] == pytest.approx(300, abs=0.1)
    assert baseline.read_bytes() == original_v2
