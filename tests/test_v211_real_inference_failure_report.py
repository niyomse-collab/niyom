"""Failure-report contract; no fake engine is treated as real inference."""
import json
from pathlib import Path

import pytest
from PIL import Image

from tools import v211_four_engine_real_inference_qa as qa


def test_failure_records_engine_and_never_claims_inference(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    Image.new("RGBA", (8, 8), (20, 30, 40, 128)).save(source)
    output_dir = tmp_path / "results"

    def fail(_source: Path, _destination: Path):
        raise RuntimeError("deliberate test failure")

    # This is a failure-path unit test, NOT real model inference.
    monkeypatch.setattr(qa, "load_real_engine_manifest", lambda _: object())
    monkeypatch.setattr(
        qa, "make_processors",
        lambda _: {engine: fail for engine in qa.ENGINES},
    )
    # A broken individual engine no longer aborts the whole set. Every
    # engine should be attempted and all failures recorded independently.
    result = qa.run(tmp_path / "unused.json", source, output_dir)
    assert result["completed_engine_count"] == 0
    report = json.loads((output_dir / "real_inference_report.json").read_text())
    assert report["real_inference_verified"] is False
    assert report["quality_improvement_verified"] is False
    assert set(report["failures"]) == set(qa.ENGINES)
    assert all(entry["error_type"] == "RuntimeError" for entry in report["failures"].values())
    assert report["engines"] == {}
