"""V2.1.1 four-model automatic integration; test doubles never certify AI."""
from pathlib import Path

from PIL import Image

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
