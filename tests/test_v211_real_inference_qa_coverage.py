"""Exercise real-inference QA evidence logic without claiming real AI ran."""
import json

import pytest
from PIL import Image

from tools import v211_four_engine_real_inference_qa as qa
from tools.v211_four_engine_subprocess import ENGINES


def _source(tmp_path, rgba=False):
    src = tmp_path / "artwork.png"
    mode = "RGBA" if rgba else "RGB"
    color = (20, 80, 120, 97) if rgba else (20, 80, 120)
    Image.new(mode, (24, 16), color).save(src, dpi=(300, 300))
    return src


def _prepare(monkeypatch, *, failed_engine=None, wrong_geometry=None):
    calls = []

    def factory(_manifest):
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination, *, engine=name):
                calls.append(engine)
                if engine == failed_engine:
                    raise RuntimeError("simulated Vulkan unavailable")
                with Image.open(source) as image:
                    size = (48, 32) if engine != wrong_geometry else (47, 32)
                    resampled = image.resize(size, Image.Resampling.LANCZOS)
                    resampled.save(destination, dpi=(300, 300))
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(qa, "load_real_engine_manifest", lambda *_: {"test": "fake manifest"})
    monkeypatch.setattr(qa, "make_processors", factory)
    return calls


def test_all_four_candidates_valid_no_visual_certification(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch)
    source = _source(tmp_path)
    result = qa.run(tmp_path / "manifest.json", source, tmp_path / "outputs")
    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is True
    assert result["quality_improvement_verified"] is False
    assert result["completed_engine_count"] == 4
    assert not result["failures"]
    assert json.loads((tmp_path / "outputs" / "real_inference_report.json").read_text())["completed_engine_count"] == 4


def test_one_failure_does_not_hide_other_three_engine_results(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch, failed_engine="real_esrgan")
    source = _source(tmp_path)
    result = qa.run(tmp_path / "manifest.json", source, tmp_path / "outputs")
    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is False
    assert result["completed_engine_count"] == 3
    assert set(result["failures"]) == {"real_esrgan"}
    assert (tmp_path / "outputs" / "anime4k.png").is_file()


def test_wrong_geometry_is_not_inference_success(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch, wrong_geometry="anime4k")
    result = qa.run(tmp_path / "manifest.json", _source(tmp_path), tmp_path / "out")
    assert calls == list(ENGINES)
    assert result["completed_engine_count"] == 3
    assert result["real_inference_verified"] is False
    assert "anime4k" in result["failures"]


def test_alpha_image_qa_uses_original_cutout(tmp_path, monkeypatch):
    _prepare(monkeypatch)
    result = qa.run(tmp_path / "manifest.json", _source(tmp_path, rgba=True), tmp_path / "out")
    assert result["real_inference_verified"] is True
    assert result["engines"]["anime4k"]["alpha_preserved"] is True


def test_preflight_fail_does_not_claim_execution(tmp_path, monkeypatch):
    def bad(_manifest):
        raise ValueError("bad model hashes")
    monkeypatch.setattr(qa, "load_real_engine_manifest", bad)
    with pytest.raises(ValueError):
        qa.run(tmp_path / "manifest.json", _source(tmp_path), tmp_path / "out")
    report = json.loads((tmp_path / "out" / "real_inference_report.json").read_text())
    assert report["real_inference_verified"] is False
    assert report["failed_stage"] == "manifest_preflight"
