"""Regression: palette PNG transparency must not be silently certified."""
from pathlib import Path
import pytest
from PIL import Image
from tools import v211_four_engine_real_inference_qa as qa


def test_palette_trns_fails_closed_before_engine_execution(tmp_path: Path, monkeypatch):
    source = tmp_path / "palette.png"
    image = Image.new("P", (4, 4), 0)
    image.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    image.save(source, transparency=0)
    class NoRun:
        def __call__(self, *_args, **_kwargs):
            pytest.fail("engine must not run on palette transparency")
    monkeypatch.setattr(qa, "load_real_engine_manifest", lambda _: {})
    monkeypatch.setattr(qa, "make_processors", lambda _: {engine: NoRun() for engine in qa.ENGINES})
    with pytest.raises(ValueError, match="palette/tRNS"):
        qa.run(tmp_path / "dummy.json", source, tmp_path / "output")
    import json
    report = json.loads((tmp_path / "output" / "real_inference_report.json").read_text())
    assert report["real_inference_verified"] is False
    assert report["failed_stage"] == "source_preflight"
