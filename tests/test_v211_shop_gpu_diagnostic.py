import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from tools import v211_shop_gpu_diagnostic as diagnostic
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand


def _gpu():
    return {
        "nvidia_smi": {"available": True, "success": True, "devices": [{
            "name": "NVIDIA GeForce GTX 1660 Ti",
            "driver_version": "32.0.16.1742",
            "memory_total_mib": 6144,
            "memory_free_mib": 5500,
        }]},
        "vulkaninfo": {"available": True, "success": True,
                       "device_names": ["NVIDIA GeForce GTX 1660 Ti"],
                       "api_versions": ["1.3.0"]},
        "vulkan_device_inventory": [{
            "index": 0,
            "name": "NVIDIA GeForce GTX 1660 Ti",
            "vendor_id": 0x10DE,
            "device_id": 0x2184,
        }],
        "vulkan_device_index": 0,
        "vulkan_target_device_match_count": 1,
        "gtx_1660_ti_detected_by_nvidia_smi": True,
        "gtx_1660_ti_detected_by_vulkan": True,
        "vulkan_loader_available": True,
        "vulkaninfo_succeeded": True,
        "vulkan_device_inventory_succeeded": True,
        "vulkan_inventory_source": "vulkaninfo",
        "vram_budget_6gb_detected": True,
    }


def _anime():
    return {
        "status": "ok",
        "processor_probe": {"success": True},
        "device_probe": {"success": True},
        "available_processors": ["cpu", "opencl", "cuda"],
        "device_inventory_by_processor": {
            "cuda": [{"index": 0, "name": "NVIDIA GeForce GTX 1660 Ti"}],
            "opencl": [{"index": 0, "name": "Intel Graphics"}],
        },
        "recommended_gpu_processor_device": {
            "processor": "cuda",
            "device_index": 0,
            "device_name": "NVIDIA GeForce GTX 1660 Ti",
        },
    }


def _write_manifest(path):
    path.write_text(json.dumps({
        name: {
            "executable": f"C:/Niyom/{name}.exe",
            "args": ["-i", "{input}", "-o", "{output}"],
        }
        for name in ENGINES
    }), encoding="utf-8")
    return path


def _verified_anime4k_command(executable):
    return {
        "anime4k": EngineCommand((
            str(executable), "-i", "{input}", "-o", "{output}", "-f", "2",
        ))
    }


def _successful_runner(manifest, source, output, *, timeout_seconds):
    assert timeout_seconds == 180
    try:
        bound = json.loads(Path(manifest).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        bound = None
    if bound is not None:
        for name in ("real_esrgan", "waifu2x", "real_cugan"):
            args = bound[name]["args"]
            assert args[args.index("-g") + 1] == "0"
        anime_args = bound["anime4k"]["args"]
        assert anime_args[anime_args.index("-p") + 1] == "cuda"
        assert anime_args[anime_args.index("-d") + 1] == "0"
    with Image.open(source) as image:
        assert image.format == "PNG"
        assert image.info.get("icc_profile")
        assert image.info.get("dpi") is not None
        rgba = image.mode == "RGBA"
    return {
        "real_inference_verified": True,
        "completed_engine_count": 4,
        "engines": {
            name: {
                "status": "binary_executed_and_2x_output_validated",
                "size": [256, 192],
                "mode": "RGBA" if rgba else "RGB",
                "sha256": "a" * 64,
                "alpha_pixels_match_source": rgba,
                "icc_preserved": True,
                "dpi_preserved": True,
            } for name in ENGINES
        },
        "failures": {},
    }


def test_anime4k_probe_reports_processors_and_devices_without_claiming_selection(
    tmp_path, monkeypatch
):
    executable = tmp_path / "ac_cli.exe"
    executable.write_bytes(b"synthetic executable placeholder")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "anime4k": {
            "executable": str(executable),
            "args": ["-i", "{input}", "-o", "{output}", "-f", "2"],
        }
    }), encoding="utf-8")

    calls = []
    order = []

    def verified_manifest(_path):
        order.append("manifest_preflight")
        return _verified_anime4k_command(executable)

    def fake_probe(path, args, timeout=15):
        order.append("binary_probe")
        calls.append((Path(path).name, args))
        if args == ["--lp"]:
            return {
                "available": True, "success": True, "status": "ok",
                "return_code": 0,
                "stdout": "Available processors: CPU OpenCL CUDA",
                "stderr": "",
            }
        return {
            "available": True, "success": True, "status": "ok",
            "return_code": 0,
            "stdout": "Device 0: NVIDIA GeForce GTX 1660 Ti",
            "stderr": "",
        }

    monkeypatch.setattr(diagnostic, "load_real_engine_manifest", verified_manifest)
    monkeypatch.setattr(diagnostic, "_run_probe", fake_probe)
    result = diagnostic.probe_anime4k_backend(manifest)

    assert order == ["manifest_preflight", "binary_probe", "binary_probe"]
    assert result["manifest_preflight_passed"] is True
    assert calls == [("ac_cli.exe", ["--lp"]), ("ac_cli.exe", ["-l"])]
    assert result["status"] == "ok"
    assert result["available_processors"] == ["cpu", "opencl", "cuda"]
    assert result["gtx_1660_ti_visible_in_device_inventory"]
    assert result["configured_processor"] == "auto"
    assert result["configured_device"] == 0
    assert result["processor_selection_verified"] is False
    assert result["device_selection_verified"] is False


def test_anime4k_probe_fails_closed_for_unreadable_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("not json", encoding="utf-8")
    result = diagnostic.probe_anime4k_backend(manifest)
    assert result["status"] == "manifest_preflight_failed"
    assert result["error_type"] == "JSONDecodeError"


def test_anime4k_probe_never_executes_an_unverified_manifest_binary(
    tmp_path, monkeypatch
):
    calls = []

    def reject_manifest(_path):
        raise ValueError("pinned executable hash mismatch")

    def forbidden_probe(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("unverified Anime4K executable must never be launched")

    monkeypatch.setattr(diagnostic, "load_real_engine_manifest", reject_manifest)
    monkeypatch.setattr(diagnostic, "_run_probe", forbidden_probe)
    result = diagnostic.probe_anime4k_backend(tmp_path / "tampered-manifest.json")

    assert result == {
        "status": "manifest_preflight_failed",
        "error_type": "ValueError",
    }
    assert calls == []


def test_nvidia_smi_parser_handles_csv_device_names():
    parsed = diagnostic._parse_nvidia_smi_csv(
        '"NVIDIA GeForce GTX 1660 Ti", 32.0.16.1742, 6144, 5500\n'
    )
    assert parsed == [{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": "32.0.16.1742",
        "memory_total_mib": 6144,
        "memory_free_mib": 5500,
    }]


def test_native_vulkan_enumerator_returns_structured_result():
    result = diagnostic._enumerate_vulkan_devices_native()

    assert isinstance(result, dict)
    assert "success" in result
    assert "status" in result
    if result["success"]:
        assert result["source"] == "vulkan_loader_native"
        assert result["device_inventory"]
        assert all(
            isinstance(item["index"], int) and item["name"]
            for item in result["device_inventory"]
        )


def test_vulkan_summary_parser_extracts_device_and_api():
    parsed = diagnostic._parse_vulkan_summary(
        "deviceName = NVIDIA GeForce GTX 1660 Ti\napiVersion = 1.3.0\n"
    )
    assert parsed["device_names"] == ["NVIDIA GeForce GTX 1660 Ti"]
    assert parsed["api_versions"] == ["1.3.0"]
    assert parsed["device_inventory"] == [{
        "index": 0, "name": "NVIDIA GeForce GTX 1660 Ti"
    }]


def test_vulkan_summary_keeps_same_model_names_at_distinct_indexes():
    parsed = diagnostic._parse_vulkan_summary(
        "GPU0:\n  deviceName = NVIDIA GeForce GTX 1660 Ti\n"
        "GPU1:\n  deviceName = NVIDIA GeForce GTX 1660 Ti\n"
    )
    assert parsed["device_inventory"] == [
        {"index": 0, "name": "NVIDIA GeForce GTX 1660 Ti"},
        {"index": 1, "name": "NVIDIA GeForce GTX 1660 Ti"},
    ]


def test_vulkan_device_properties_decoder_reads_nvidia_adapter():
    raw = bytearray(1024)
    struct.pack_into("<IIIII", raw, 0, 1 << 22, 12, 0x10DE, 0x2184, 1)
    raw[20:20 + len(b"NVIDIA GeForce GTX 1660 Ti\0")] = b"NVIDIA GeForce GTX 1660 Ti\0"

    parsed = diagnostic._decode_vulkan_device_properties(bytes(raw), 2)

    assert parsed["index"] == 2
    assert parsed["name"] == "NVIDIA GeForce GTX 1660 Ti"
    assert parsed["vendor_id"] == 0x10DE
    assert parsed["device_type"] == 1


def test_probe_gpu_uses_native_vulkan_loader_when_vulkaninfo_is_missing(
    monkeypatch,
):
    def find_tool(name):
        return "nvidia-smi.exe" if name == "nvidia-smi" else None

    def run_probe(executable, args, timeout=15):
        if executable == "nvidia-smi.exe":
            return {
                "available": True, "success": True, "status": "ok",
                "stdout": '"NVIDIA GeForce GTX 1660 Ti", 32.0.16.1742, 6144, 5500\n',
                "stderr": "",
            }
        return {"available": False, "success": False, "status": "not_found"}

    monkeypatch.setattr(diagnostic, "_find_tool", find_tool)
    monkeypatch.setattr(diagnostic, "_run_probe", run_probe)
    monkeypatch.setattr(diagnostic, "_probe_vulkan_loader", lambda: True)
    monkeypatch.setattr(diagnostic, "_enumerate_vulkan_devices_native", lambda: {
        "available": True, "success": True, "status": "ok",
        "source": "vulkan_loader_native",
        "device_inventory": [{
            "index": 1, "name": "NVIDIA GeForce GTX 1660 Ti",
            "vendor_id": 0x10DE, "device_id": 0x2184, "device_type": 1,
        }],
        "device_names": ["NVIDIA GeForce GTX 1660 Ti"],
    })

    report = diagnostic.probe_gpu()

    assert report["gtx_1660_ti_detected_by_nvidia_smi"]
    assert report["gtx_1660_ti_detected_by_vulkan"]
    assert report["vulkaninfo_succeeded"] is False
    assert report["vulkan_device_inventory_succeeded"] is True
    assert report["vulkan_inventory_source"] == "vulkan_loader_native"
    assert report["vulkan_device_index"] == 1
    assert report["vulkan_device_inventory"][0]["name"] == "NVIDIA GeForce GTX 1660 Ti"
    assert report["vulkaninfo"]["success"] is False
    assert report["vulkaninfo"]["inventory_source"] == "vulkan_loader_native"
    # Native loader inventory is sufficient for device binding; the optional
    # SDK command must not be falsely reported as executed.
    from tools.v211_gpu_device_binding import resolve_device_selection
    assert resolve_device_selection(report, _anime())["binding_configured"]


def test_anime4k_probe_maps_nvidia_device_by_processor(tmp_path, monkeypatch):
    executable = tmp_path / "ac_cli.exe"
    executable.write_bytes(b"synthetic executable placeholder")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "anime4k": {
            "executable": str(executable),
            "args": ["-i", "{input}", "-o", "{output}", "-f", "2"],
        }
    }), encoding="utf-8")

    def fake_probe(path, args, timeout=15):
        if args == ["--lp"]:
            return {
                "available": True, "success": True, "status": "ok",
                "return_code": 0,
                "stdout": "Processors:\n  auto Auto\n  cpu CPU\n  opencl OpenCL\n  cuda CUDA\n",
                "stderr": "",
            }
        return {
            "available": True, "success": True, "status": "ok",
            "return_code": 0,
            "stdout": (
                "Devices:\nCPU:\n  [0] x86 CPU\n"
                "OpenCL:\n  [0] Intel Graphics\n"
                "CUDA:\n  [0] NVIDIA GeForce GTX 1660 Ti (6144MB, CC 7.5)\n"
            ),
            "stderr": "",
        }

    monkeypatch.setattr(
        diagnostic,
        "load_real_engine_manifest",
        lambda _path: _verified_anime4k_command(executable),
    )
    monkeypatch.setattr(diagnostic, "_run_probe", fake_probe)
    result = diagnostic.probe_anime4k_backend(manifest)

    assert result["manifest_preflight_passed"] is True
    assert result["device_inventory_by_processor"]["cuda"] == [{
        "index": 0, "name": "NVIDIA GeForce GTX 1660 Ti"
    }]
    assert result["recommended_gpu_processor_device"] == {
        "processor": "cuda",
        "device_index": 0,
        "device_name": "NVIDIA GeForce GTX 1660 Ti",
    }
    assert result["processor_selection_verified"] is False
    assert result["device_selection_verified"] is False


def test_synthetic_pngs_include_rgb_rgba_icc_and_300dpi(tmp_path):
    rgb = tmp_path / "rgb.png"
    rgba = tmp_path / "rgba.png"
    diagnostic.create_synthetic_png(rgb, rgba=False)
    diagnostic.create_synthetic_png(rgba, rgba=True)
    with Image.open(rgb) as image:
        assert image.mode == "RGB"
        assert image.info.get("icc_profile")
        assert all(abs(value - 300.0) < 0.01 for value in image.info["dpi"])
    with Image.open(rgba) as image:
        assert image.mode == "RGBA"
        assert image.info.get("icc_profile")
        assert all(abs(value - 300.0) < 0.01 for value in image.info["dpi"])
        assert image.getchannel("A").getextrema()[0] == 0


def test_local_diagnostic_runs_all_four_on_both_synthetic_cases(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu, engine_runner=_successful_runner,
        anime4k_probe=lambda _manifest: _anime(),
    )
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert report["gtx_1660_ti_and_vulkan_environment_detected"]
    assert report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"]
    assert report["device_binding_applied"] is True
    assert report["device_binding"]["ncnn_vulkan"]["device_index"] == 0
    assert report["device_binding"]["anime4k"]["backend"] == "cuda"
    assert all(item["both_cases_pass"] for item in report["engine_matrix"].values())
    assert report["quality_improvement_verified"] is False
    assert report["customer_artwork_used"] is False
    assert report["network_accessed"] is False
    assert report["uploads_performed"] is False
    assert report["images_retained"] is False
    assert sorted(p.name for p in (tmp_path / "report").iterdir()) == [
        "shop_gpu_diagnostic.json"
    ]
    saved = json.loads(
        (tmp_path / "report" / "shop_gpu_diagnostic.json").read_text(encoding="utf-8")
    )
    assert saved["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert saved["anime4k_backend_inventory"]["status"] == "ok"
    assert saved["schema_version"] == 4
    assert saved["vulkaninfo_succeeded"] is True
    assert saved["vulkan_device_inventory_succeeded"] is True
    assert saved["vulkan_inventory_source"] == "vulkaninfo"
    assert saved["three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host"]
    assert saved["anime4k_cli_outputs_validated_on_both_synthetic_cases"]
    assert saved["anime4k_backend_selection_verified"] is False
    assert all(
        value is False
        for value in saved["per_engine_backend_selection_verified"].values()
    )



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gtx_1660_ti_detected_by_nvidia_smi", False),
        ("gtx_1660_ti_detected_by_vulkan", False),
        ("vulkan_device_index", None),
        ("vulkan_loader_available", False),
        ("vulkan_device_inventory_succeeded", False),
        ("vram_budget_6gb_detected", False),
    ],
)
def test_gpu_readiness_requires_real_vulkan_adapter_and_vram(
    tmp_path, field, value
):
    gpu = _gpu()
    gpu[field] = value
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test manifest", encoding="utf-8")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=lambda: gpu, engine_runner=_successful_runner,
        bind_devices=False,
    )
    # Engine output validity and target-machine readiness are independent.
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["gtx_1660_ti_and_vulkan_environment_detected"]
    assert not report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"]


def test_gpu_readiness_accepts_native_loader_inventory_without_vulkaninfo(
    tmp_path,
):
    gpu = _gpu()
    gpu["vulkaninfo_succeeded"] = False
    gpu["vulkan_device_inventory_succeeded"] = True
    gpu["vulkan_inventory_source"] = "vulkan_loader_native"
    gpu["vulkaninfo"]["success"] = False
    gpu["vulkaninfo"]["inventory_source"] = "vulkan_loader_native"
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test manifest", encoding="utf-8")

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=lambda: gpu, engine_runner=_successful_runner,
        bind_devices=False,
    )

    assert report["vulkaninfo_succeeded"] is False
    assert report["vulkan_device_inventory_succeeded"] is True
    assert report["vulkan_inventory_source"] == "vulkan_loader_native"
    assert report["gtx_1660_ti_and_vulkan_environment_detected"] is True


@pytest.mark.parametrize(("target_gpu_ready", "expected_exit"), [(False, 1), (True, 0)])
def test_cli_exit_code_requires_target_gpu_readiness(
    monkeypatch, tmp_path, target_gpu_ready, expected_exit
):
    report = {
        "all_four_native_cli_outputs_validated_on_both_synthetic_cases": True,
        "four_engine_cli_passed_on_gtx1660ti_vulkan_host": target_gpu_ready,
    }
    calls = []

    def fake_run(manifest, output_dir, *, timeout_seconds):
        calls.append((manifest, output_dir, timeout_seconds))
        return report

    monkeypatch.setattr(diagnostic, "run_diagnostic", fake_run)
    assert diagnostic.main([
        "--manifest", str(tmp_path / "manifest.json"),
        "--output-dir", str(tmp_path / "report"),
        "--timeout-seconds", "123",
    ]) == expected_exit
    assert calls == [(
        tmp_path / "manifest.json",
        tmp_path / "report",
        123,
    )]


def test_cli_help_lists_all_supported_options(capsys):
    with pytest.raises(SystemExit) as exc:
        diagnostic.main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for option in ("--manifest", "--output-dir", "--timeout-seconds"):
        assert option in help_text


def test_one_engine_failure_is_not_reported_as_four_engine_success(tmp_path):
    def one_engine_fails(manifest, source, output, *, timeout_seconds):
        result = _successful_runner(
            manifest, source, output, timeout_seconds=timeout_seconds
        )
        result["real_inference_verified"] = False
        result["completed_engine_count"] = 3
        result["engines"]["waifu2x"]["status"] = "failed"
        result["failures"] = {
            "waifu2x": {"error_type": "RuntimeError", "error_class": "subprocess_or_candidate_failure"}
        }
        return result

    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu, engine_runner=one_engine_fails,
        anime4k_probe=lambda _manifest: _anime(),
    )
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["engine_matrix"]["waifu2x"]["both_cases_pass"]
    assert report["quality_improvement_verified"] is False


def test_invalid_manifest_exception_fails_closed_without_retaining_images(tmp_path):
    def bad_manifest(manifest, source, output, *, timeout_seconds):
        raise ValueError("bad manifest")

    report = diagnostic.run_diagnostic(
        tmp_path / "missing.json", tmp_path / "report",
        gpu_probe=_gpu, engine_runner=bad_manifest,
        bind_devices=False,
    )
    assert not report["manifest_preflight_passed"]
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert report["cases"]["rgb_icc_dpi"]["failure_type"] == "ValueError"
    assert sorted(p.name for p in (tmp_path / "report").iterdir()) == [
        "shop_gpu_diagnostic.json"
    ]


def test_timeout_bounds_are_validated(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="timeout_seconds"):
        diagnostic.run_diagnostic(
            tmp_path / "manifest.json", tmp_path / "report",
            gpu_probe=_gpu, engine_runner=_successful_runner,
            timeout_seconds=0,
        )



def test_anime4k_failure_is_separate_from_three_ncnn_vulkan_engine_gate(tmp_path):
    def anime4k_fails(manifest, source, output, *, timeout_seconds):
        result = _successful_runner(
            manifest, source, output, timeout_seconds=timeout_seconds
        )
        result["real_inference_verified"] = False
        result["completed_engine_count"] = 3
        result["engines"]["anime4k"]["status"] = "failed"
        result["failures"] = {
            "anime4k": {
                "error_type": "RuntimeError",
                "error_class": "subprocess_or_candidate_failure",
            }
        }
        return result

    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu, engine_runner=anime4k_fails,
        anime4k_probe=lambda _manifest: _anime(),
    )

    assert report["three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host"]
    assert not report["anime4k_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"]
    assert report["engine_backend_expectations"]["anime4k"]["expected_backend"].startswith(
        "Anime4KCPP CUDA/OpenCL"
    )


def test_ncnn_failure_blocks_three_engine_vulkan_host_gate(tmp_path):
    def ncnn_fails(manifest, source, output, *, timeout_seconds):
        result = _successful_runner(
            manifest, source, output, timeout_seconds=timeout_seconds
        )
        result["real_inference_verified"] = False
        result["completed_engine_count"] = 3
        result["engines"]["waifu2x"]["status"] = "failed"
        result["failures"] = {
            "waifu2x": {
                "error_type": "RuntimeError",
                "error_class": "vulkan_initialization_failed",
            }
        }
        return result

    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu, engine_runner=ncnn_fails,
        anime4k_probe=lambda _manifest: _anime(),
    )

    assert report["anime4k_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host"]
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert all(
        value is False
        for value in report["per_engine_backend_selection_verified"].values()
    )


def test_frozen_exe_diagnostic_dispatch_is_before_editor_and_packaged():
    """The documented one-command shop QA must work in the frozen EXE."""
    root = Path(__file__).resolve().parents[1]
    run_source = (root / "run.py").read_text(encoding="utf-8")
    spec_source = (root / "NiyomsilV2ArmCore.spec").read_text(encoding="utf-8")

    dispatch = 'if len(sys.argv) >= 2 and sys.argv[1] == "--diagnose-v211-four-ai":'
    editor_import = "from signprint_ai.app_v2 import main"
    assert dispatch in run_source
    assert run_source.index(dispatch) < run_source.index(editor_import)
    assert "diagnostic_main(sys.argv[2:])" in run_source
    assert '"tools.v211_shop_gpu_diagnostic"' in run_source
    assert '"tools.v211_shop_gpu_diagnostic"' in spec_source


def test_windows_candidate_smokes_frozen_diagnostic_dispatch_without_running_gpu_qa():
    """The windowed frozen EXE is waited on through its Process exit code."""
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github" / "workflows" / "v211-four-engine-bridge-windows.yml"
    ).read_text(encoding="utf-8")
    assert "Verify packaged GTX 1660 Ti diagnostic command dispatch (help only)" in workflow
    assert "--diagnose-v211-four-ai', '--help" in workflow
    assert "Start-Process -FilePath $exe" in workflow
    assert "$process.ExitCode" in workflow
    assert "$LASTEXITCODE" not in workflow
    assert "Packaged diagnostic help failed with exit code" in workflow
