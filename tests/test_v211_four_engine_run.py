"""End-to-end smoke test for four-engine runner using local fake executables.

This tests wiring and image validation only; it does not claim real AI inference.
"""
import json
import sys

import pytest

from PIL import Image

from tools.v211_four_engine_run import run
from tools.v211_four_engine_coordinator import run_candidates
from tools.v211_four_engine_subprocess import ENGINES


def test_four_engine_runner_produces_four_valid_candidates(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    code = (
        "import sys; from PIL import Image; "
        "im=Image.open(sys.argv[1]); im.save(sys.argv[2])"
    )
    config = tmp_path / "engines.json"
    config.write_text(
        json.dumps({
            name: [sys.executable, "-c", code, "{input}", "{output}"]
            for name in ENGINES
        }), encoding="utf-8"
    )
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert result["ready_for_fusion_research"]
    assert not result["fusion_implemented"]
    assert not result["quality_certified"]
    assert set(result["candidates"]) == set(ENGINES)
    assert not result["failures"]
    for output in result["candidates"].values():
        with Image.open(output) as image:
            assert image.size == (8, 8)
            assert image.mode == "RGB"
    report = json.loads((tmp_path / "outputs" / "four_engine_report.json").read_text(encoding="utf-8"))
    assert report["ready_for_fusion_research"]


def test_runner_reports_failed_engine(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8)).save(source)
    code = "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])"
    config = tmp_path / "engines.json"
    commands = {
        name: [sys.executable, "-c", code, "{input}", "{output}"]
        for name in ENGINES
    }
    commands["anime4k"] = [sys.executable, "-c", "import sys;sys.exit(4)", "{input}", "{output}"]
    config.write_text(json.dumps(commands), encoding="utf-8")
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert not result["ready_for_fusion_research"]
    assert "anime4k" in result["failures"]
    assert len(result["candidates"]) == 3



def test_coordinator_cancellation_removes_already_completed_candidate_files(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    output_dir = tmp_path / "cancelled-output"
    calls = []

    def processor(src, destination):
        calls.append(destination.name)
        with Image.open(src) as image:
            image.save(destination)

    processors = {name: processor for name in ENGINES}

    with pytest.raises(InterruptedError, match="stopped"):
        run_candidates(
            source, output_dir, (8, 8), processors,
            cancel_check=lambda: bool(calls),
        )

    assert calls == ["real_esrgan.png"]
    assert not list(output_dir.glob("*.png"))
