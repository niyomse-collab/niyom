"""V2.1.1 four-model automatic integration; test doubles never certify AI."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageCms

from signprint_ai import niyomsil_core_adapter as adapter_module
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter

from signprint_ai import v211_four_engine_bridge as bridge
from tools import v211_four_engine_run


import pytest


@pytest.fixture(autouse=True)
def _stub_runtime_device_binding(monkeypatch):
    def prepare(_manifest_path, work_dir):
        bound = Path(work_dir) / "manifest.runtime-bound.json"
        bound.write_text("{}", encoding="utf-8")
        return bound, {
            "binding_configured": True,
            "runtime_device_use_verified": False,
            "ncnn_vulkan": {"device_index": 0, "device_name": "NVIDIA GeForce GTX 1660 Ti"},
            "anime4k": {"backend": "cuda", "device_index": 0,
                        "device_name": "NVIDIA GeForce GTX 1660 Ti"},
        }
    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", prepare)


def _source_and_v2(tmp_path):
    source, baseline = tmp_path / "source.png", tmp_path / "approved-V2.png"
    Image.new("RGB", (8, 8), (30, 100, 50)).save(source, dpi=(300, 300))
    Image.new("RGB", (16, 16), (30, 100, 50)).save(baseline, dpi=(300, 300))
    return source, baseline


def test_installed_four_ai_is_auto_executed_and_exports_separate_result(tmp_path, monkeypatch):
    original, v2 = _source_and_v2(tmp_path)
    before = v2.read_bytes()
    root = tmp_path / "local-app-data"
    manifest = root / "NiyomSilp" / "V211-FourAI-QA" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("test-stub-manifest; no real models", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(root))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    calls = []

    def fake_runner(src, output_dir, config, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(src) as seed, Image.open(v2_reference) as reference:
            calls.append((seed.size, config, size, real_engines, reference.size))
            fusion = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fusion, dpi=(300, 300))
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "engine_pixel_effect_verified": {n: True for n in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
                "engine_pixel_effect_pixels": {n: 1 for n in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
                "output": str(fusion),
                "mean_abs_detail_delta": 1.5,
                "engine_detail_contribution_mean_abs": {
                    n: .1 for n in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
                },
                "protected_faces_preserved": True,
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_runner)
    report = bridge.maybe_run_four_engine_assist(original, v2)
    assert report["status"] == "four_engine_fusion_preview_ready"
    assert report["fusion_implemented"] is True
    assert report["quality_certified"] is False
    assert report["completed_engine_count"] == 4
    fused = Path(report["four_engine_fusion_output"])
    assert fused.is_file()
    assert fused != v2
    assert fused.parent == v2.parent
    assert ".V211-4AI-QA-" in fused.name
    assert v2.read_bytes() == before
    assert calls == [((8, 8), manifest, (16, 16), True, (16, 16))]
    assert Image.open(fused).size == (16, 16)


def test_no_installed_four_ai_leaves_v2_untouched(tmp_path, monkeypatch):
    src, v2 = _source_and_v2(tmp_path)
    before = v2.read_bytes()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "empty"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    result = bridge.maybe_run_four_engine_assist(src, v2)
    assert result["status"] == "models_not_installed"
    assert v2.read_bytes() == before


def test_auto_face_preserved_when_no_bounding_boxes(tmp_path, monkeypatch):
    src, v2 = _source_and_v2(tmp_path)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "stub.json"))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    observed = []

    def capture(_src, _out, _config, _size, **kwargs):
        observed.append(kwargs)
        return {"ready_for_fusion_research": False, "completed_engine_count": 0}

    monkeypatch.setattr(v211_four_engine_run, "run", capture)
    report = bridge.maybe_run_four_engine_assist(
        src, v2, preserve_all_v2_faces=True,
    )
    assert report["status"] == "incomplete_four_engine_candidates"
    assert observed[0]["preserve_all_v2_faces"] is True
    assert observed[0]["real_engines"] is True


def test_custom_four_x_target_runs_native_two_x_on_half_target_seed(tmp_path, monkeypatch):
    src, v2 = _source_and_v2(tmp_path)
    Image.new("RGB", (32, 32), (35, 80, 120)).save(v2)
    before = v2.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "stub.json"))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    observed = {}

    def fake_run(seed, output_dir, config, size, *, real_engines, v2_reference, **kwargs):
        with Image.open(seed) as image:
            observed["seed_size"] = image.size
        with Image.open(v2_reference) as reference:
            observed["reference_size"] = reference.size
            fusion = Path(output_dir) / "four_engine_fused_preview.png"
            reference.save(fusion)
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {"fusion_implemented": True, "all_four_engine_pixels_contributed": True, "output": str(fusion)},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(src, v2)
    assert result["status"] == "four_engine_fusion_preview_ready"
    assert observed == {"seed_size": (16, 16), "reference_size": (32, 32)}
    assert result["four_engine_fusion_details"]["native_engine_scale"] == 2
    assert v2.read_bytes() == before



def test_core_adapter_maps_face_regions_to_final_fit_canvas(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "accepted-V2.png"
    source_icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (8, 8), (35, 80, 120)).save(
        source, dpi=(300, 300), icc_profile=source_icc
    )
    selected = ((0.25, 0.25, 0.75, 0.75),)

    class FakeEngine:
        def enhance(self, src, out, *, scale, progress_callback=None, cancel_check=None):
            assert scale == 2
            with Image.open(src) as image:
                image.resize((16, 16), Image.Resampling.LANCZOS).save(out, dpi=(300, 300))

    class FakeFaceModule:
        def apply(self, image, **kwargs):
            assert kwargs["regions"] == selected
            return image, SimpleNamespace(as_dict=lambda: {
                "enabled": True, "applied": True, "face_count": 1,
                "mode": "protect", "strength": 35,
                "skipped_reason": None, "face_audit": [],
            })

    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(name="CPU")
        ),
    )
    adapter.face_module = FakeFaceModule()
    adapter.create_job_engine = lambda settings: FakeEngine()

    monkeypatch.setattr(adapter_module, "image_size", lambda path: (8, 8))
    monkeypatch.setattr(adapter_module, "needs_streaming", lambda *args: False)
    monkeypatch.setattr(adapter_module, "print_pixels", lambda *args: (16, 8))
    monkeypatch.setattr(adapter_module, "validate_export", lambda *args: None)
    monkeypatch.setattr(adapter_module, "refine_sign_edges", lambda image, **kwargs: image)
    from signprint_ai import v211_blur_gate, v211_face_contract
    monkeypatch.setattr(
        v211_blur_gate, "select_photo_restoration",
        lambda settings, source_path, **kwargs: (settings, None),
    )
    monkeypatch.setattr(
        v211_face_contract, "enforce_requested_face_restoration",
        lambda *args, **kwargs: None,
    )

    qa = tmp_path / "accepted-V2.V211-4AI-QA-test.png"
    Image.new("RGB", (16, 8), (200, 30, 40)).save(qa)
    observed = {}

    def fake_bridge(src, v2_output, **kwargs):
        assert Path(v2_output).is_file(), "bridge must run only after V2 is durable"
        with Image.open(v2_output) as saved:
            assert saved.size == (16, 8)
            assert saved.getpixel((8, 4)) == (35, 80, 120)
            assert saved.info.get("icc_profile") == source_icc
        observed["source"] = Path(src)
        observed["v2_output"] = Path(v2_output)
        observed["kwargs"] = kwargs
        return {
            "status": "four_engine_fusion_preview_ready",
            "four_engine_fusion_output": str(qa),
            "fusion_implemented": True,
            "quality_certified": False,
            "v2_output_preserved": True,
        }

    from signprint_ai import v211_four_engine_bridge
    monkeypatch.setattr(v211_four_engine_bridge, "maybe_run_four_engine_assist", fake_bridge)

    settings = SimpleNamespace(
        print_width=1.0, print_height=0.5, print_unit="cm", dpi=300,
        ai_scale=2, color_mode="RGB", resize_mode="fit",
        device="AUTO", face_protection=True, face_mode="protect",
        face_strength=35, face_regions=selected, graphic_ai=False,
        text_graphic_boost=0, icc_profile_path=None,
        v211_photo_model="real_esrgan",
    )
    result = adapter.process(source, destination, settings, use_ai=True)

    assert destination.is_file()
    assert result["four_engine_research"]["four_engine_fusion_output"] == str(qa)
    assert observed["source"] == source
    assert observed["v2_output"] == destination
    assert observed["kwargs"]["use_ai"] is True
    assert observed["kwargs"]["cancel"] is None
    assert observed["kwargs"]["protected_regions"] == ((0.375, 0.25, 0.625, 0.75),)
    assert observed["kwargs"]["preserve_all_v2_faces"] is False
    assert observed["kwargs"]["resize_mode"] == "fit"
    assert qa.is_file()
    with Image.open(destination) as saved, Image.open(qa) as preview:
        assert saved.size == (16, 8)
        assert saved.getpixel((8, 4)) == (35, 80, 120)
        assert saved.info.get("icc_profile") == source_icc
        assert preview.size == (16, 8)
        assert preview.getpixel((0, 0)) == (200, 30, 40)

def test_disk_tiled_v2_job_runs_four_engine_bridge_when_within_auxiliary_budget(
    tmp_path, monkeypatch
):
    source, destination = _source_and_v2(tmp_path)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    observed = {}

    monkeypatch.setattr(adapter_module, "image_size", lambda _path: (1200, 1200))
    monkeypatch.setattr(adapter_module, "needs_streaming", lambda *args: True)
    monkeypatch.setattr(adapter_module, "validate_export", lambda *args: None)

    def fake_large(_adapter, _src, dst, _settings, source_size, target_size,
                   _scale, progress, _cancel, _use_ai, **kwargs):
        observed["large_path"] = (source_size, target_size, progress is not None)
        Path(dst).write_bytes(b"durable V2 raster")
        return {"output": str(dst), "face_protection": {"applied": False}}

    def fake_photo_preflight(settings, source_path, **kwargs):
        return settings, None

    monkeypatch.setattr(adapter_module, "process_large", fake_large)
    from signprint_ai import v211_blur_gate
    monkeypatch.setattr(
        v211_blur_gate, "select_photo_restoration", fake_photo_preflight
    )

    def fake_bridge(src, v2_output, **kwargs):
        assert Path(v2_output).read_bytes() == b"durable V2 raster"
        observed["bridge"] = (Path(src), Path(v2_output), kwargs)
        return {
            "status": "four_engine_fusion_preview_ready",
            "v2_output_preserved": True,
            "quality_certified": False,
        }

    monkeypatch.setattr(bridge, "maybe_run_four_engine_assist", fake_bridge)
    settings = SimpleNamespace(
        print_width=None, print_height=None, ai_scale=2,
        v211_source_guided_ink=False, face_protection=False,
        face_regions=(), resize_mode="fit",
    )
    result = adapter.process(source, destination, settings, use_ai=True)

    assert observed["large_path"][:2] == ((1200, 1200), (2400, 2400))
    assert observed["bridge"][0] == source
    assert observed["bridge"][1] == destination
    assert observed["bridge"][2]["preserve_all_v2_faces"] is False
    assert observed["bridge"][2]["resize_mode"] == "fit"
    assert result["four_engine_research"]["status"] == "four_engine_fusion_preview_ready"
    assert destination.read_bytes() == b"durable V2 raster"


def test_disk_tiled_v2_job_over_18mp_keeps_four_engine_route_pending(
    tmp_path, monkeypatch
):
    source, destination = _source_and_v2(tmp_path)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    monkeypatch.setattr(adapter_module, "image_size", lambda _path: (4000, 3000))
    monkeypatch.setattr(adapter_module, "needs_streaming", lambda *args: True)
    monkeypatch.setattr(adapter_module, "validate_export", lambda *args: None)

    def fake_large(_adapter, _src, dst, _settings, _source_size, _target_size,
                   _scale, _progress, _cancel, _use_ai, **kwargs):
        Path(dst).write_bytes(b"durable large V2 raster")
        return {"output": str(dst), "face_protection": {"applied": False}}

    monkeypatch.setattr(adapter_module, "process_large", fake_large)
    from signprint_ai import v211_blur_gate
    monkeypatch.setattr(
        v211_blur_gate, "select_photo_restoration",
        lambda settings, source_path, **kwargs: (settings, None),
    )

    def bridge_must_not_run(*args, **kwargs):
        raise AssertionError("18MP+ auxiliary job must remain fail-closed until tile streaming exists")

    monkeypatch.setattr(bridge, "maybe_run_four_engine_assist", bridge_must_not_run)
    settings = SimpleNamespace(
        print_width=None, print_height=None, ai_scale=2,
        v211_source_guided_ink=False, face_protection=False,
        face_regions=(), resize_mode="stretch",
    )
    result = adapter.process(source, destination, settings, use_ai=True)

    assert result["four_engine_research"]["status"] == "large_image_tiling_pending"
    assert result["four_engine_research"]["source_pixels"] == 12_000_000
    assert result["four_engine_research"]["target_pixels"] == 48_000_000
    assert destination.read_bytes() == b"durable large V2 raster"
