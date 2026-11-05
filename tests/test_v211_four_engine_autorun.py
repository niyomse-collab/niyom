"""V2.1.1 four-model automatic integration; test doubles never certify AI."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageCms

from signprint_ai import niyomsil_core_adapter as adapter_module
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter

from signprint_ai import v211_four_engine_bridge as bridge
from tools import v211_four_engine_run


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
        calls.append((src, config, size, real_engines, v2_reference))
        fusion = Path(output_dir) / "four_engine_fused_preview.png"
        with Image.open(v2) as image:
            image.save(fusion, dpi=(300, 300))
        return {
            "ready_for_fusion_research": True,
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
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
    assert calls == [(original, manifest, (16, 16), True, v2)]
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


def test_cannot_automatically_run_four_ai_for_non_2x_job(tmp_path, monkeypatch):
    src, v2 = _source_and_v2(tmp_path)
    Image.new("RGB", (32, 32)).save(v2)
    before = v2.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "stub.json"))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    def unexpected(*args, **kwargs):
        raise AssertionError("incorrect scale")
    monkeypatch.setattr(v211_four_engine_run, "run", unexpected)
    result = bridge.maybe_run_four_engine_assist(src, v2)
    assert result["status"] == "auxiliary_engine_scale_mismatch"
    assert v2.read_bytes() == before



def test_core_adapter_runs_bridge_after_durable_v2_png_save(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "accepted-V2.png"
    source_icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (8, 8), (35, 80, 120)).save(
        source, dpi=(300, 300), icc_profile=source_icc
    )

    class FakeEngine:
        def enhance(self, src, out, *, scale, progress_callback=None, cancel_check=None):
            assert scale == 2
            with Image.open(src) as image:
                image.resize((16, 16), Image.Resampling.LANCZOS).save(out, dpi=(300, 300))

    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(name="CPU")
        ),
    )
    adapter.face_module = object()
    adapter.create_job_engine = lambda settings: FakeEngine()

    monkeypatch.setattr(adapter_module, "image_size", lambda path: (8, 8))
    monkeypatch.setattr(adapter_module, "needs_streaming", lambda *args: False)
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
    Image.new("RGB", (16, 16), (200, 30, 40)).save(qa)
    observed = {}

    def fake_bridge(src, v2_output, **kwargs):
        assert Path(v2_output).is_file(), "bridge must run only after V2 is durable"
        with Image.open(v2_output) as saved:
            assert saved.size == (16, 16)
            assert saved.getpixel((0, 0)) == (35, 80, 120)
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
        print_width=None, print_height=None, print_unit="cm", dpi=300,
        ai_scale=2, color_mode="RGB", resize_mode="stretch",
        device="AUTO", face_protection=False, face_mode="protect",
        face_strength=35, face_regions=(), graphic_ai=False,
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
    assert qa.is_file()
    with Image.open(destination) as saved, Image.open(qa) as preview:
        assert saved.getpixel((0, 0)) == (35, 80, 120)
        assert saved.info.get("icc_profile") == source_icc
        assert preview.getpixel((0, 0)) == (200, 30, 40)
