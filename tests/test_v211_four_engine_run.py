"""End-to-end smoke test for four-engine runner using local fake executables.

This tests wiring and image validation only; it does not claim real AI inference.
"""
import json
import sys

import pytest

from PIL import Image

from tools.v211_four_engine_run import run, _privacy_safe_report
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
    commands = {}
    for name in ENGINES:
        device_args = (
            ["-g", "0"] if name in ("real_esrgan", "waifu2x", "real_cugan")
            else ["-p", "cuda", "-d", "0"]
        )
        commands[name] = [
            sys.executable, "-c", code, "{input}", "{output}", *device_args
        ]
    config.write_text(json.dumps(commands), encoding="utf-8")
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert result["ready_for_fusion_research"]
    assert not result["fusion_implemented"]
    assert not result["quality_certified"]
    assert set(result["candidates"]) == set(ENGINES)
    assert not result["failures"]
    assert result["runtime_device_use_verified"] is False
    assert "physical adapter use" in result["execution_evidence_scope"]
    assert set(result["engine_execution"]) == set(ENGINES)
    for name, evidence in result["engine_execution"].items():
        process = evidence["process"]
        assert process["status"] == "output_ready"
        assert process["process_started"] is True
        assert isinstance(process["pid"], int) and process["pid"] > 0
        assert process["exit_code"] == 0
        assert process["process_elapsed_ms"] >= 0
        assert evidence["runtime_device_use_verified"] is False
        assert evidence["device_configuration"]["explicitly_configured"] is True
        assert evidence["device_configuration"]["actual_adapter_verified"] is False
        assert not ({"argv", "stdout", "stderr", "source", "destination"} & set(process))
    assert result["engine_execution"]["real_esrgan"]["device_configuration"] == {
        "backend": "ncnn_vulkan", "device_index": 0,
        "explicitly_configured": True, "actual_adapter_verified": False,
    }
    assert result["engine_execution"]["anime4k"]["device_configuration"] == {
        "backend": "cuda", "device_index": 0,
        "explicitly_configured": True, "actual_adapter_verified": False,
    }
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
    commands["anime4k"] = [
        sys.executable, "-c",
        "import sys;print(sys.argv[1], file=sys.stderr);sys.exit(4)",
        "{input}", "{output}",
    ]
    config.write_text(json.dumps(commands), encoding="utf-8")
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert not result["ready_for_fusion_research"]
    assert "anime4k" in result["failures"]
    assert len(result["candidates"]) == 3
    execution = result["engine_execution"]
    assert execution["anime4k"]["process"]["status"] == "process_failed"
    assert execution["anime4k"]["process"]["process_started"] is True
    assert execution["anime4k"]["process"]["exit_code"] == 4
    assert all(
        execution[name]["process"]["status"] == "output_ready"
        for name in ENGINES if name != "anime4k"
    )
    assert result["real_engine_inference_proven"] is False
    assert result["failures"]["anime4k"]["details_redacted"] is True
    assert result["failures"]["anime4k"]["error_type"] == "RuntimeError"
    persisted = (tmp_path / "outputs" / "four_engine_report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in persisted
    assert "stderr" not in persisted
    assert "candidate_files" in json.loads(persisted)
    assert "candidates" not in json.loads(persisted)


def test_privacy_safe_report_redacts_nested_output_paths(tmp_path):
    report = {
        "candidates": {"real_esrgan": str(tmp_path / "engine" / "real_esrgan.png")},
        "failures": {"waifu2x": "RuntimeError: private stderr " + str(tmp_path)},
        "three_engine_priority_preview": {
            "selected": "real_esrgan",
            "output": str(tmp_path / "preview.png"),
        },
        "four_engine_fusion": {
            "fusion_implemented": True,
            "output": str(tmp_path / "fused.png"),
        },
        "fusion_error": "OSError: " + str(tmp_path / "private"),
    }
    safe = _privacy_safe_report(report)
    serialized = json.dumps(safe)
    assert str(tmp_path) not in serialized
    assert "private stderr" not in serialized
    assert safe["candidate_files"] == {"real_esrgan": "real_esrgan.png"}
    assert safe["three_engine_priority_preview"]["output_filename"] == "preview.png"
    assert safe["four_engine_fusion"]["output_filename"] == "fused.png"
    assert safe["fusion_error"]["details_redacted"] is True



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
