import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from tools.v211_gpu_device_binding import (
    GPUDeviceBindingError, MIN_FREE_VRAM_MIB, validate_free_vram_report,
)
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors
from tools.v211_four_engine_run import run
from tools import v211_shop_gpu_diagnostic as diagnostic
from signprint_ai import v211_four_engine_bridge as bridge


def _gpu_report(free=5600):
    return {"nvidia_smi": {"success": True, "devices": [{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "memory_total_mib": 6144, "memory_free_mib": free,
    }]}}


def test_shared_free_vram_validator_enforces_exact_target_and_threshold():
    assert validate_free_vram_report(_gpu_report())["passed"] is True
    with pytest.raises(GPUDeviceBindingError, match="insufficient free VRAM"):
        validate_free_vram_report(_gpu_report(MIN_FREE_VRAM_MIB - 1))
    ambiguous = _gpu_report()
    ambiguous["nvidia_smi"]["devices"].append(dict(ambiguous["nvidia_smi"]["devices"][0]))
    with pytest.raises(GPUDeviceBindingError, match="exactly one"):
        validate_free_vram_report(ambiguous)


def test_lightweight_probe_uses_only_nvidia_smi_and_drops_raw_output(monkeypatch):
    calls = []
    def fake_probe(executable, args, timeout=15):
        calls.append((executable, args, timeout))
        return {
            "available": True, "success": True, "status": "ok", "return_code": 0,
            "stdout": "NVIDIA GeForce GTX 1660 Ti, 32.0.16.1742, 6144, 4096\n",
            "stderr": "private raw diagnostic",
        }
    monkeypatch.setattr(diagnostic, "_find_tool", lambda _name: "nvidia-smi.exe")
    monkeypatch.setattr(diagnostic, "_run_probe", fake_probe)
    result = diagnostic.probe_nvidia_smi_memory()
    assert calls[0][0] == "nvidia-smi.exe"
    assert "memory.free" in calls[0][1][0]
    assert result["nvidia_smi"]["devices"][0]["memory_free_mib"] == 4096
    assert "stdout" not in result["nvidia_smi"]
    assert "stderr" not in result["nvidia_smi"]


def test_subprocess_guard_blocks_before_popen_when_vram_drops(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    marker = tmp_path / "launched.txt"
    destination = tmp_path / "blocked.png"
    script = (
        "import pathlib,sys; pathlib.Path(sys.argv[2]).write_text('started'); "
        "pathlib.Path(sys.argv[3]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    )
    commands = {
        name: EngineCommand((sys.executable, "-c", script, "{input}", "{output}", str(marker)))
        for name in ENGINES
    }
    records = {}
    def blocked(_engine):
        raise GPUDeviceBindingError("insufficient free VRAM")
    with pytest.raises(GPUDeviceBindingError):
        make_processors(commands, pre_launch_check=blocked, execution_records=records)["real_esrgan"](
            source, destination
        )
    record = records["real_esrgan"]
    assert record["status"] == "preflight_failed"
    assert record["process_started"] is False
    assert record["pre_launch_vram_checks"] == 1
    assert not marker.exists()
    assert not destination.exists()


def test_subprocess_guard_records_only_safe_snapshot_fields(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    code = "import pathlib,sys; pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    commands = {name: EngineCommand((sys.executable, "-c", code, "{input}", "{output}")) for name in ENGINES}
    records = {}
    snapshot = {
        "total_mib": 6144, "free_mib": 4096,
        "minimum_free_mib": 2048, "passed": True, "private": "do-not-copy",
    }
    make_processors(commands, pre_launch_check=lambda _name: snapshot, execution_records=records)[
        "real_esrgan"
    ](source, tmp_path / "out.png")
    record = records["real_esrgan"]
    assert record["pre_launch_vram"] == {
        "passed": True, "free_mib": 4096, "minimum_free_mib": 2048,
    }
    assert record["pre_launch_vram_min_free_mib"] == 4096
    assert "private" not in str(record)


def test_runner_rechecks_before_each_of_four_processes(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    code = "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])"
    config = tmp_path / "engines.json"
    config.write_text(json.dumps({
        name: [sys.executable, "-c", code, "{input}", "{output}"] for name in ENGINES
    }), encoding="utf-8")
    checked = []
    def check(name):
        checked.append(name)
        return {"total_mib": 6144, "free_mib": 4096, "minimum_free_mib": 2048, "passed": True}
    result = run(
        source, tmp_path / "outputs", config, (8, 8),
        real_engines=False, pre_launch_check=check,
    )
    assert checked == list(ENGINES)
    assert result["completed_engine_count"] == 4
    for name in ENGINES:
        assert result["engine_execution"][name]["process"]["pre_launch_vram"]["passed"] is True


@pytest.fixture(autouse=True)
def _stub_runtime_binding(monkeypatch):
    def prepare(_manifest, work_dir):
        bound = Path(work_dir) / "manifest.runtime-bound.json"
        bound.write_text("{}", encoding="utf-8")
        return bound, {"binding_configured": True, "runtime_device_use_verified": False}
    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", prepare)


def test_application_bridge_supplies_per_process_vram_guard(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    baseline = tmp_path / "V2.png"
    Image.new("RGBA", (8, 8), (20, 30, 40, 120)).save(source)
    Image.new("RGBA", (16, 16), (30, 40, 50, 120)).save(baseline)
    before = baseline.read_bytes()
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)
    calls = []
    def guard(name):
        calls.append(name)
        return {"total_mib": 6144, "free_mib": 4096, "minimum_free_mib": 2048, "passed": True}
    monkeypatch.setattr(bridge, "_prelaunch_vram_check", guard)
    from tools import v211_four_engine_run
    def fake_run(src, output_dir, manifest, size, *, real_engines, v2_reference, **kwargs):
        callback = kwargs["pre_launch_check"]
        assert callback is guard
        assert callback("real_esrgan")["passed"] is True
        fused = Path(output_dir) / "four_engine_fused_preview.png"
        with Image.open(v2_reference) as image:
            image.save(fused)
        return {
            "ready_for_fusion_research": True, "completed_engine_count": 4,
            "runtime_device_use_verified": True,
            "per_engine_runtime_device_use_verified": {name: True for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")},
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "all_four_engine_pixels_contributed": True,
                "output": str(fused),
            },
        }
    monkeypatch.setattr(v211_four_engine_run, "run", fake_run)
    result = bridge.maybe_run_four_engine_assist(source, baseline)
    assert calls == ["real_esrgan"]
    assert result["v2_output_preserved"] is True
    assert result["status"] == "four_engine_fusion_preview_ready"
    assert baseline.read_bytes() == before
