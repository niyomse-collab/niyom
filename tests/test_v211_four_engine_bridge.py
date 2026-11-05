"""The four-engine bridge must be opt-in and must never rewrite V2."""
from pathlib import Path

from PIL import Image

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


def test_non_png_output_keeps_v2(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    tiff = tmp_path / "out.tiff"
    tiff.write_bytes(b"unchanged-print-export")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", "test-manifest.json")
    assert bridge.maybe_run_four_engine_assist(source, tiff)["status"] == "unsupported_output_format"
    assert tiff.read_bytes() == b"unchanged-print-export"


def test_fake_runner_cannot_replace_v2_output(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    old = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    from tools import v211_four_engine_run
    calls = []
    def stub(src, output_dir, manifest, size, *, real_engines, v2_reference):
        calls.append((src, size, real_engines, v2_reference))
        return {"ready_for_fusion_research": True, "completed_engine_count": 4, "failures": {}}
    monkeypatch.setattr(v211_four_engine_run, "run", stub)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "candidate_research_complete"
    assert result["quality_certified"] is False
    assert result["fusion_implemented"] is False
    assert result["v2_output_preserved"]
    assert calls == [(source, (16, 16), True, baseline)]
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


def test_opt_in_skips_unsupported_four_times_scale_without_running_engines(tmp_path, monkeypatch):
    source, baseline = _images(tmp_path)
    with Image.open(baseline) as image:
        rgba = image.copy()
    rgba.resize((32, 32), Image.Resampling.LANCZOS).save(baseline)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    from tools import v211_four_engine_run

    def must_not_run(*args, **kwargs):
        raise AssertionError("2x auxiliary engines must never launch for 4x V2")

    monkeypatch.setattr(v211_four_engine_run, "run", must_not_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert result["status"] == "auxiliary_engine_scale_mismatch"
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
