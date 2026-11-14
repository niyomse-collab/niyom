"""Unit tests for four-engine command adapters (no checkpoints required)."""
import sys
import time
from pathlib import Path

import pytest

from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors


def test_requires_all_four():
    with pytest.raises(ValueError, match="four"):
        make_processors({"waifu2x": EngineCommand(("echo", "{input}", "{output}"))})


def test_missing_placeholders_rejected():
    with pytest.raises(ValueError, match="output"):
        EngineCommand(("echo", "{input}"))


def test_four_real_subprocess_invocations(tmp_path):
    source = tmp_path / "source.png"
    from PIL import Image
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = "import pathlib,sys; pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    processors = make_processors(commands)
    for engine in ENGINES:
        target = tmp_path / (engine + ".png")
        processors[engine](source, target)
        with Image.open(target) as output:
            assert output.size == (4, 4)
            assert output.getpixel((0, 0)) == (20, 40, 60)


def test_execution_records_capture_pid_exit_and_elapsed_without_command_paths(tmp_path):
    from PIL import Image
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = (
        "import pathlib,sys; "
        "pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    )
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    records = {}
    processors = make_processors(commands, execution_records=records)
    destination = tmp_path / "telemetry.png"
    processors["real_esrgan"](source, destination)

    record = records["real_esrgan"]
    assert record["status"] == "output_ready"
    assert record["process_started"] is True
    assert isinstance(record["pid"], int) and record["pid"] > 0
    assert record["exit_code"] == 0
    assert record["process_elapsed_ms"] >= 0
    assert record["elapsed_ms_total"] >= record["process_elapsed_ms"]
    assert "argv" not in record
    assert "stdout" not in record
    assert "stderr" not in record


def test_timeout_records_process_exit_and_uses_timeout_error(tmp_path):
    from PIL import Image
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = "import time; time.sleep(10)"
    commands = {
        engine: EngineCommand(
            (sys.executable, "-c", script, "{input}", "{output}"),
            timeout_seconds=0.15,
        )
        for engine in ENGINES
    }
    records = {}
    processor = make_processors(commands, execution_records=records)["real_esrgan"]
    with pytest.raises(TimeoutError, match="timed out"):
        processor(source, tmp_path / "timeout.png")
    record = records["real_esrgan"]
    assert record["status"] == "timed_out"
    assert record["process_started"] is True
    assert isinstance(record["pid"], int)
    assert record["elapsed_ms_total"] >= 0
    assert not (tmp_path / "timeout.png").exists()



def test_real_portable_engine_runs_with_models_relative_to_its_binary(tmp_path, monkeypatch):
    from PIL import Image
    from tools import v211_four_engine_subprocess as module
    install = tmp_path / "Portable" / "bin"
    install.mkdir(parents=True)
    executable = install / "realesrgan-ncnn-vulkan.exe"
    executable.write_bytes(b"hash-pinned test placeholder, not real inference")
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (50, 70, 90)).save(source)
    destination = tmp_path / "output.png"
    calls = []

    class FakeProcess:
        pid = 12345
        returncode = 0
        def poll(self):
            return self.returncode
        def communicate(self, timeout=None):
            return ("", "")
        def wait(self, timeout=None):
            return self.returncode

    def stub(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["cwd"] == str(install.resolve())
        assert kwargs["shell"] is False
        Image.open(source).save(destination)
        return FakeProcess()

    monkeypatch.setattr(module.subprocess, "Popen", stub)
    commands = {
        name: EngineCommand((str(executable), "-i", "{input}", "-o", "{output}"))
        for name in ENGINES
    }
    module.make_processors(commands)["real_esrgan"](source, destination)
    assert len(calls) == 1
    assert destination.is_file()



def test_cancel_before_launch_does_not_start_native_process(tmp_path):
    from PIL import Image
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    marker = tmp_path / "launched.txt"
    destination = tmp_path / "cancelled.png"
    script = (
        "import pathlib,sys; pathlib.Path(sys.argv[2]).write_text('started'); "
        "pathlib.Path(sys.argv[3]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    )
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}", str(marker)))
        for engine in ENGINES
    }
    processor = make_processors(commands, cancel_check=lambda: True)["real_esrgan"]
    with pytest.raises(InterruptedError, match="stopped"):
        processor(source, destination)
    assert not marker.exists()
    assert not destination.exists()


def test_cancel_terminates_active_native_process_and_removes_partial_output(tmp_path):
    from PIL import Image
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    destination = tmp_path / "cancelled.png"
    script = (
        "import pathlib,sys,time; pathlib.Path(sys.argv[2]).write_text('partial'); "
        "time.sleep(10)"
    )
    commands = {
        engine: EngineCommand(
            (sys.executable, "-c", script, "{input}", "{output}"),
            timeout_seconds=20,
        )
        for engine in ENGINES
    }
    started = time.monotonic()
    records = {}
    processor = make_processors(
        commands,
        cancel_check=lambda: time.monotonic() - started >= 0.25,
        execution_records=records,
    )["real_esrgan"]
    with pytest.raises(InterruptedError, match="stopped"):
        processor(source, destination)
    assert records["real_esrgan"]["status"] == "cancelled"
    assert records["real_esrgan"]["process_started"] is True
    assert not destination.exists()



def test_runtime_vram_guard_terminates_native_process_above_six_gib_budget(tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    destination = tmp_path / "over-budget.png"
    script = "import time; time.sleep(10)"
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    mib = 1024 * 1024
    safe = {
        "verified": True,
        "status": "verified",
        "adapter_name": "NVIDIA GeForce GTX 1660 Ti",
        "adapter_index": 0,
        "backend_apis": ["graphics"],
        "device_memory_available": True,
        "device_memory_status": "ok",
        "device_memory_total_bytes": 8192 * mib,
        "device_memory_used_bytes": 5632 * mib,
        "device_memory_free_bytes": 2560 * mib,
    }
    over = {
        **safe,
        "device_memory_used_bytes": 5633 * mib,
        "device_memory_free_bytes": 2559 * mib,
    }
    samples = iter((safe, over))
    probe_calls = []

    def probe(pid, engine):
        probe_calls.append((pid, engine))
        return next(samples)

    records = {}
    processor = make_processors(
        commands,
        execution_records=records,
        runtime_device_probe=probe,
        runtime_vram_guard=True,
        runtime_vram_budget_mib=6144,
        runtime_vram_reserve_mib=512,
    )["real_esrgan"]

    with pytest.raises(RuntimeError, match="6 GiB device-wide VRAM budget exceeded"):
        processor(source, destination)

    record = records["real_esrgan"]
    assert len(probe_calls) == 2
    assert record["status"] == "vram_guard_device_budget_exceeded"
    assert record["runtime_vram_guard_status"] == "device_budget_exceeded"
    assert record["runtime_vram_budget_mib"] == 6144
    assert record["runtime_vram_max_allowed_device_used_mib"] == 5632.0
    assert record["runtime_vram_max_device_used_mib"] == 5632.0
    assert record["runtime_vram_peak_used_mib"] == 5633.0
    assert record["runtime_vram_sample_count"] == 2
    assert not destination.exists()


def test_runtime_vram_guard_rejects_invalid_budget_policy():
    commands = {
        engine: EngineCommand((sys.executable, "-c", "pass", "{input}", "{output}"))
        for engine in ENGINES
    }
    with pytest.raises(ValueError, match="device budget"):
        make_processors(
            commands,
            runtime_device_probe=lambda _pid, _engine: {},
            runtime_vram_guard=True,
            runtime_vram_budget_mib=512,
        )


def test_runtime_adapter_probe_is_sampled_while_process_runs_and_recorded(tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = (
        "import pathlib,sys,time; "
        "pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes()); "
        "time.sleep(0.15)"
    )
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    calls = []

    def verified_probe(pid, engine):
        calls.append((pid, engine))
        return {
            "available": True,
            "verified": True,
            "status": "verified",
            "adapter_name": "NVIDIA GeForce GTX 1660 Ti",
            "adapter_index": 0,
            "backend_apis": ["graphics"],
            "used_gpu_memory_bytes": 1024 * 1024,
        }

    records = {}
    processor = make_processors(
        commands,
        execution_records=records,
        runtime_device_probe=verified_probe,
    )["real_esrgan"]
    processor(source, tmp_path / "verified.png")

    record = records["real_esrgan"]
    assert calls
    assert all(pid > 0 and engine == "real_esrgan" for pid, engine in calls)
    assert record["runtime_device_use_verified"] is True
    assert record["runtime_device_all_processes_verified"] is True
    assert record["runtime_device_process_count"] == 1
    assert record["runtime_device_verified_process_count"] == 1
    assert record["runtime_device_sample_count"] >= 1
    assert record["runtime_adapter_name"] == "NVIDIA GeForce GTX 1660 Ti"
    assert record["runtime_adapter_index"] == 0
    assert record["runtime_adapter_backend_apis"] == ["graphics"]


def test_runtime_adapter_acceptance_fails_closed_when_any_tile_process_is_unverified(tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = (
        "import pathlib,sys; "
        "pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    )
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    probe_results = iter([
        {"verified": True, "status": "verified", "adapter_name": "NVIDIA GeForce GTX 1660 Ti",
         "adapter_index": 0, "backend_apis": ["compute"]},
        {"verified": False, "status": "pid_not_observed"},
    ])

    def alternating_probe(pid, engine):
        return next(probe_results)

    records = {}
    processor = make_processors(
        commands,
        execution_records=records,
        runtime_device_probe=alternating_probe,
    )["real_esrgan"]
    processor(source, tmp_path / "first.png")
    processor(source, tmp_path / "second.png")

    record = records["real_esrgan"]
    assert record["runtime_device_process_count"] == 2
    assert record["runtime_device_verified_process_count"] == 1
    assert record["runtime_device_all_processes_verified"] is False
    assert record["runtime_device_use_verified"] is False



def test_runtime_adapter_conflict_invalidates_an_earlier_positive_sample(tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = "import time,sys; time.sleep(0.15)"
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    samples = iter([
        {
            "verified": True,
            "status": "verified",
            "adapter_name": "NVIDIA GeForce GTX 1660 Ti",
            "adapter_index": 0,
            "backend_apis": ["graphics"],
        },
        {"verified": False, "status": "pid_seen_on_wrong_adapter"},
    ])

    def conflicting_probe(pid, engine):
        return next(samples)

    records = {}
    processor = make_processors(
        commands,
        execution_records=records,
        runtime_device_probe=conflicting_probe,
    )["real_esrgan"]
    with pytest.raises(RuntimeError):
        processor(source, tmp_path / "conflict.png")

    record = records["real_esrgan"]
    assert record["runtime_device_probe_conflict"] is True
    assert record["runtime_device_all_processes_verified"] is False
    assert record["runtime_device_use_verified"] is False
