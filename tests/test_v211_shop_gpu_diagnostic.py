import json
import os
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
            "driver_version": "570.65",
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
        "manifest_preflight_passed": True,
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



def _successful_bridge_runner(source, baseline, *, use_ai, resize_mode):
    assert use_ai is True
    assert resize_mode == "stretch"
    evidence = Path(os.environ["NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR"])
    run_dir = evidence / "synthetic-bridge"
    run_dir.mkdir(parents=True)
    output = run_dir / "fused.png"
    with Image.open(baseline) as image:
        image.load()
        metadata = {
            key: image.info[key]
            for key in ("icc_profile", "dpi")
            if key in image.info
        }
        image.save(output, format="PNG", **metadata)
    (run_dir / "four_engine_report.json").write_text(
        json.dumps({
            "engine_execution": {
                name: {
                    "process": {
                        "pre_launch_vram_checks": 1,
                        "pre_launch_vram_min_free_mib": 4096,
                    }
                }
                for name in ENGINES
            }
        }),
        encoding="utf-8",
    )
    return {
        "status": "four_engine_fusion_preview_ready",
        "completed_engine_count": 4,
        "four_engine_fusion_output": str(output),
        "fusion_implemented": True,
        "all_four_engine_pixels_contributed": True,
        "engine_pixel_effect_pixels": {name: 12 for name in ENGINES},
        "engine_pixel_effect_verified": {name: True for name in ENGINES},
        "device_binding": {"binding_configured": True},
        "quality_certified": False,
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
                "stdout": '"NVIDIA GeForce GTX 1660 Ti", 570.65, 6144, 5500\n',
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
    assert report["cuda_12_8_driver_compatibility"]["status"] == "full_cuda_12_8_ga_driver_compatible"
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




def test_full_bridge_fusion_integration_requires_all_four_pixel_effects_and_v2_safety(
    tmp_path,
):
    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=_successful_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=_successful_bridge_runner,
    )
    bridge = report["bridge_integration"]
    assert bridge["passed"] is True, bridge
    assert bridge["case"] == "rgba_alpha_icc_dpi"
    assert bridge["completed_engine_count"] == 4
    assert bridge["fusion_implemented"] is True
    assert bridge["all_four_engine_pixels_contributed"] is True
    assert all(bridge["engine_pixel_effect_verified"].values())
    assert bridge["pre_launch_vram_checks_passed"] is True
    assert bridge["v2_baseline_unchanged"] is True
    assert bridge["source_unchanged"] is True
    assert all(bridge["output_metadata"].values())
    assert report["four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host"] is False
    assert bridge["runtime_vram_budget_passed"] is False
    assert report["runtime_vram_budget_passed"] is False
    assert bridge["runtime_device_use_verified"] is False
    assert all(
        value is False
        for value in bridge["per_engine_runtime_device_use_verified"].values()
    )
    assert report["runtime_device_use_verified"] is False
    assert all(
        value is False
        for value in report["per_engine_runtime_device_use_verified"].values()
    )
    assert report["shop_gpu_acceptance_passed"] is False
    assert bridge["quality_certified"] is False
    assert bridge["images_retained"] is False
    payload = json.dumps(report)
    assert str(tmp_path) not in payload



def test_shop_gpu_gate_requires_native_rgb_rgba_and_bridge_fusion_together(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")

    def one_rgba_engine_fails(manifest_path, source, output, *, timeout_seconds):
        result = _successful_runner(
            manifest_path, source, output, timeout_seconds=timeout_seconds
        )
        with Image.open(source) as image:
            rgba = image.mode == "RGBA"
        if rgba:
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

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=one_rgba_engine_fails,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=_successful_bridge_runner,
    )
    assert report["bridge_integration"]["passed"] is True
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"] is False
    assert report["four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host"] is False



def test_bridge_integration_fails_closed_when_anime4k_does_not_contribute(
    tmp_path,
):
    manifest = _write_manifest(tmp_path / "manifest.json")

    def missing_anime4k(source, baseline, *, use_ai, resize_mode):
        result = _successful_bridge_runner(
            source, baseline, use_ai=use_ai, resize_mode=resize_mode
        )
        result["status"] = "four_engine_fusion_contribution_incomplete"
        result["all_four_engine_pixels_contributed"] = False
        result["engine_pixel_effect_verified"]["anime4k"] = False
        result["engine_pixel_effect_pixels"]["anime4k"] = 0
        return result

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=_successful_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=missing_anime4k,
    )
    assert report["bridge_integration"]["passed"] is False
    assert report["bridge_integration"]["engine_pixel_effect_verified"]["anime4k"] is False
    assert report["four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host"] is False


def test_bridge_integration_fails_if_accepted_v2_reference_changes(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")

    def mutates_baseline(source, baseline, *, use_ai, resize_mode):
        result = _successful_bridge_runner(
            source, baseline, use_ai=use_ai, resize_mode=resize_mode
        )
        with Image.open(baseline) as image:
            image.load()
            changed = image.copy()
            changed.putpixel((0, 0), (0, 0, 0, 0))
            metadata = {
                key: image.info[key]
                for key in ("icc_profile", "dpi")
                if key in image.info
            }
        changed.save(baseline, format="PNG", **metadata)
        changed.close()
        baseline.write_bytes(b"deliberately-corrupted-v2-reference")
        return result

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=_successful_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=mutates_baseline,
    )
    assert report["bridge_integration"]["v2_baseline_unchanged"] is False
    assert report["bridge_integration"]["passed"] is False
    assert report["four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host"] is False


def test_local_diagnostic_runs_all_four_on_both_synthetic_cases(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu, engine_runner=_successful_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
    )
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert report["gtx_1660_ti_and_vulkan_environment_detected"]
    assert report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"]
    assert report["device_binding_applied"] is True
    assert report["device_binding"]["ncnn_vulkan"]["device_index"] == 0
    assert report["device_binding"]["anime4k"]["backend"] == "cuda"
    assert all(item["both_cases_pass"] for item in report["engine_matrix"].values())
    assert report["quality_improvement_verified"] is False
    assert report["runtime_device_use_verified"] is False
    assert report["shop_gpu_acceptance_passed"] is False
    assert all(
        value is False
        for value in report["per_engine_runtime_device_use_verified"].values()
    )
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
    assert saved["schema_version"] == 7
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
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
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
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        bind_devices=False,
    )

    assert report["vulkaninfo_succeeded"] is False
    assert report["vulkan_device_inventory_succeeded"] is True
    assert report["vulkan_inventory_source"] == "vulkan_loader_native"
    assert report["gtx_1660_ti_and_vulkan_environment_detected"] is True


@pytest.mark.parametrize(
    ("target_gpu_ready", "runtime_device_use_verified", "expected_exit"),
    [(False, False, 1), (True, False, 1), (True, True, 0)],
)
def test_cli_exit_code_requires_runtime_gpu_acceptance(
    monkeypatch, tmp_path, target_gpu_ready, runtime_device_use_verified, expected_exit
):
    report = {
        "shop_gpu_acceptance_passed": bool(
            target_gpu_ready and runtime_device_use_verified
        ),
    }
    calls = []

    def fake_run(manifest, output_dir, *, timeout_seconds, integration_runner):
        calls.append((manifest, output_dir, timeout_seconds, callable(integration_runner)))
        return {
            "shop_gpu_acceptance_passed": report["shop_gpu_acceptance_passed"]
        }

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
        True,
    )]



def test_windowed_frozen_diagnostic_does_not_require_stdout(monkeypatch, tmp_path):
    calls = []

    def fake_run(manifest, output_dir, *, timeout_seconds, integration_runner):
        calls.append((manifest, output_dir, timeout_seconds, callable(integration_runner)))
        return {
            "shop_gpu_acceptance_passed": True
        }

    monkeypatch.setattr(diagnostic, "run_diagnostic", fake_run)
    monkeypatch.setattr(diagnostic.sys, "stdout", None)
    assert diagnostic.main([
        "--manifest", str(tmp_path / "manifest.json"),
        "--output-dir", str(tmp_path / "report"),
        "--timeout-seconds", "90",
    ]) == 0
    assert calls == [(
        tmp_path / "manifest.json",
        tmp_path / "report",
        90,
        True,
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
        manifest_loader=lambda _manifest: {},
    )
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert not report["engine_matrix"]["waifu2x"]["both_cases_pass"]
    assert report["quality_improvement_verified"] is False


def test_invalid_manifest_exception_fails_closed_without_retaining_images(tmp_path):
    runner_calls = []

    def bad_manifest(manifest, source, output, *, timeout_seconds):
        runner_calls.append((manifest, source, output))
        raise ValueError("bad manifest")

    report = diagnostic.run_diagnostic(
        tmp_path / "missing.json", tmp_path / "report",
        gpu_probe=_gpu, engine_runner=bad_manifest,
        bind_devices=False,
    )
    assert runner_calls == []
    assert not report["manifest_preflight_passed"]
    assert not report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert report["cases"]["rgb_icc_dpi"]["failed_stage"] == "manifest_preflight"
    assert report["cases"]["rgb_icc_dpi"]["failure_type"] == "FileNotFoundError"
    assert sorted(p.name for p in (tmp_path / "report").iterdir()) == [
        "shop_gpu_diagnostic.json"
    ]


def test_manifest_preflight_failure_cannot_be_overridden_by_fake_engine_success(tmp_path):
    manifest = tmp_path / "tampered-manifest.json"
    manifest.write_text("tampered", encoding="utf-8")
    runner_calls = []

    def fake_success(*args, **kwargs):
        runner_calls.append(args)
        return _successful_runner(*args, **kwargs)

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=fake_success,
        anime4k_probe=lambda _manifest: {
            "status": "manifest_preflight_failed",
            "manifest_preflight_passed": False,
            "error_type": "ValueError",
        },
        bind_devices=False,
    )

    # The runner must not be called at all after a failed manifest preflight.
    assert runner_calls == []
    assert report["manifest_preflight_passed"] is False
    assert report["cases"]["rgb_icc_dpi"]["failed_stage"] == "manifest_preflight"
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"] is False
    assert report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"] is False


def test_fake_anime_probe_cannot_bypass_independent_manifest_preflight(tmp_path):
    manifest = tmp_path / "tampered-manifest.json"
    manifest.write_text("tampered", encoding="utf-8")
    runner_calls = []
    probe_calls = []

    def fake_success(*args, **kwargs):
        runner_calls.append(args)
        return _successful_runner(*args, **kwargs)

    def fake_anime_probe(_manifest):
        probe_calls.append(_manifest)
        # A test hook or faulty inventory callback must not override the
        # independently verified, repository-pinned four-engine manifest.
        return {
            "status": "ok",
            "manifest_preflight_passed": True,
            "processor_probe": {"success": True},
            "device_probe": {"success": True},
        }

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=fake_success,
        anime4k_probe=fake_anime_probe,
        bind_devices=False,
    )

    assert probe_calls == []
    assert runner_calls == []
    assert report["manifest_preflight_passed"] is False
    assert report["cases"]["rgb_icc_dpi"]["failed_stage"] == "manifest_preflight"
    assert report["cases"]["rgb_icc_dpi"]["failure_type"] == "JSONDecodeError"
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"] is False
    assert report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"] is False


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
        manifest_loader=lambda _manifest: {},
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
        manifest_loader=lambda _manifest: {},
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
    diagnostic_step = workflow.split("Verify packaged GTX 1660 Ti diagnostic command dispatch (help only)", 1)[1].split("Verify candidate provenance and every installer slice SHA256", 1)[0]
    assert "$LASTEXITCODE" not in diagnostic_step
    assert "Packaged diagnostic help failed with exit code" in workflow


def test_manual_shop_gpu_evidence_workflow_is_self_hosted_and_fail_closed():
    """Manual GPU evidence must run on the shop PC, never a hosted runner."""
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github" / "workflows" / "v211-four-engine-manual-evidence.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "confirm_shop_gpu:" in workflow
    assert "default: 'no'" in workflow
    assert "inputs.confirm_shop_gpu == 'yes'" in workflow
    assert "runs-on: [self-hosted, Windows, X64, niyom-shop-gpu]" in workflow
    assert "windows-latest" not in workflow
    assert "V211_VERIFIED_MANIFEST" not in workflow
    assert "V211_QA_SOURCE" not in workflow
    assert "$env:LOCALAPPDATA" in workflow
    assert "V211-FourAI-QA\\manifest.json" in workflow
    assert "Source commit:" in workflow
    assert "$env:GITHUB_SHA" in workflow
    assert "--diagnose-v211-four-ai" in workflow
    assert "four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host" in workflow
    assert "pre_launch_vram_checks_passed" in workflow
    assert "runtime_vram_budget_passed" in workflow
    assert "customer_artwork_used" in workflow
    assert "quality_improvement_verified" in workflow
    assert "Runtime physical-adapter telemetry" in workflow

    upload_block = workflow.split("path: |", 1)[1].split("if-no-files-found:", 1)[0]
    assert "build_identity.json" in upload_block
    assert "shop_gpu_diagnostic.json" in upload_block
    assert ".png" not in upload_block.lower()
    assert ".zip" not in upload_block.lower()
    assert ".bin" not in upload_block.lower()
    assert ".pth" not in upload_block.lower()



def _runtime_verified_runner(manifest, source, output, *, timeout_seconds):
    result = _successful_runner(
        manifest, source, output, timeout_seconds=timeout_seconds
    )
    result["engines"] = {
        name: {
            **item,
            "runtime_device_use_verified": True,
            "runtime_device_telemetry": {
                "runtime_device_probe_status": "verified",
                "runtime_device_probe_conflict": False,
                "runtime_device_process_count": 1,
                "runtime_device_verified_process_count": 1,
                "runtime_device_all_processes_verified": True,
                "runtime_device_sample_count": 2,
                "runtime_device_nvml_memory_verified_process_count": 1,
                "runtime_device_wddm_pdh_verified_process_count": 0,
                "runtime_device_evidence_source": "nvml_process_memory",
                "runtime_adapter_name": "NVIDIA GeForce GTX 1660 Ti",
                "runtime_adapter_index": 0,
                "runtime_adapter_backend_apis": ["graphics"],
            },
        }
        for name, item in result["engines"].items()
    }
    return result


def _runtime_verified_bridge_runner(source, baseline, *, use_ai, resize_mode):
    result = _successful_bridge_runner(
        source, baseline, use_ai=use_ai, resize_mode=resize_mode
    )
    report_path = Path(result["four_engine_fusion_output"]).parent / "four_engine_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for name in ENGINES:
        process = report["engine_execution"][name]["process"]
        process.update({
            "runtime_device_use_verified": True,
            "runtime_device_process_count": 1,
            "runtime_device_verified_process_count": 1,
            "runtime_device_all_processes_verified": True,
            "runtime_device_sample_count": 2,
            "runtime_device_nvml_memory_verified_process_count": 1,
            "runtime_device_wddm_pdh_verified_process_count": 0,
            "runtime_device_evidence_source": "nvml_process_memory",
            "runtime_device_probe_status": "verified",
            "runtime_device_probe_conflict": False,
            "runtime_adapter_name": "NVIDIA GeForce GTX 1660 Ti",
            "runtime_adapter_index": 0,
            "runtime_adapter_backend_apis": ["graphics"],
            "runtime_vram_guard_enabled": True,
            "runtime_vram_guard_status": "within_budget",
            "runtime_vram_sample_count": 2,
            "runtime_vram_peak_used_mib": 4200.0,
            "runtime_vram_min_free_mib": 1944.0,
            "runtime_vram_max_device_used_mib": 5632.0,
            "runtime_vram_budget_mib": 6144,
        })
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return result


def test_shop_gpu_acceptance_requires_live_nvml_evidence_for_every_engine(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=_runtime_verified_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=_runtime_verified_bridge_runner,
    )

    assert report["runtime_device_use_verified"] is True
    assert all(report["per_engine_runtime_device_use_verified"].values())
    assert all(
        item["target_adapter_selection_verified"]
        for item in report["engine_backend_expectations"].values()
    )
    assert report["shop_gpu_acceptance_passed"] is True
    assert report["runtime_vram_budget_passed"] is True
    assert all(report["per_engine_runtime_vram_budget_passed"].values())
    assert report["quality_improvement_verified"] is False
    assert report["visual_quality_certified"] is False
    assert report["print_quality_certified"] is False


def test_shop_gpu_acceptance_fails_if_one_engine_exceeds_runtime_vram_budget(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")

    def one_engine_over_budget(source, baseline, *, use_ai, resize_mode):
        result = _runtime_verified_bridge_runner(
            source, baseline, use_ai=use_ai, resize_mode=resize_mode
        )
        report_path = Path(result["four_engine_fusion_output"]).parent / "four_engine_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        process = report["engine_execution"]["waifu2x"]["process"]
        process["runtime_vram_guard_status"] = "device_budget_exceeded"
        process["runtime_vram_peak_used_mib"] = 5700.0
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return result

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=_runtime_verified_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=one_engine_over_budget,
    )
    assert report["runtime_vram_budget_passed"] is False
    assert report["per_engine_runtime_vram_budget_passed"]["waifu2x"] is False
    assert report["shop_gpu_acceptance_passed"] is False


def test_shop_gpu_acceptance_fails_if_one_native_engine_lacks_runtime_evidence(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")

    def one_engine_not_seen(manifest_path, source, output, *, timeout_seconds):
        result = _runtime_verified_runner(
            manifest_path, source, output, timeout_seconds=timeout_seconds
        )
        result["engines"]["waifu2x"]["runtime_device_use_verified"] = False
        result["engines"]["waifu2x"]["runtime_device_telemetry"][
            "runtime_device_probe_status"
        ] = "pid_not_observed"
        return result

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=one_engine_not_seen,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
        integration_runner=_runtime_verified_bridge_runner,
    )

    assert report["runtime_device_use_verified"] is False
    assert report["per_engine_runtime_device_use_verified"]["waifu2x"] is False
    assert report["shop_gpu_acceptance_passed"] is False


def test_runtime_evidence_accepts_wddm_only_with_per_process_gpu_engine_activity():
    telemetry = {
        "runtime_device_process_count": 2,
        "runtime_device_verified_process_count": 2,
        "runtime_device_all_processes_verified": True,
        "runtime_device_sample_count": 5,
        "runtime_device_probe_status": "verified",
        "runtime_device_probe_conflict": False,
        "runtime_device_nvml_memory_verified_process_count": 0,
        "runtime_device_wddm_pdh_verified_process_count": 2,
        "runtime_device_evidence_source": "nvml_pid_plus_windows_gpu_engine_pdh",
        "runtime_gpu_engine_min_sample_count": 2,
        "runtime_gpu_engine_min_active_sample_count": 1,
        "runtime_gpu_engine_max_utilization_percent": 3.5,
        "runtime_gpu_engine_adapter_luid_match": True,
        "runtime_gpu_engine_adapter_luid": "0x00000000_0x0000e7f7",
        "runtime_adapter_name": "NVIDIA GeForce GTX 1660 Ti",
        "runtime_adapter_index": 0,
        "runtime_adapter_backend_apis": ["graphics", "compute"],
    }

    assert diagnostic._runtime_device_evidence_verified(True, telemetry) is True

    telemetry["runtime_gpu_engine_min_sample_count"] = 1
    assert diagnostic._runtime_device_evidence_verified(True, telemetry) is False

    telemetry["runtime_gpu_engine_min_sample_count"] = 2
    telemetry["runtime_gpu_engine_min_active_sample_count"] = 0
    assert diagnostic._runtime_device_evidence_verified(True, telemetry) is False

    telemetry["runtime_gpu_engine_min_active_sample_count"] = 1
    telemetry["runtime_device_wddm_pdh_verified_process_count"] = 1
    assert diagnostic._runtime_device_evidence_verified(True, telemetry) is False

    telemetry["runtime_device_wddm_pdh_verified_process_count"] = 2
    telemetry["runtime_gpu_engine_adapter_luid_match"] = False
    assert diagnostic._runtime_device_evidence_verified(True, telemetry) is False



@pytest.mark.parametrize(
    ("driver", "status", "minor_compatible", "full_12_8"),
    [
        ("451.67", "below_cuda_12x_minor_compatibility_floor", False, False),
        ("528.33", "minor_compatibility_only_full_cuda_12_8_driver_not_met", True, False),
        ("560.94", "minor_compatibility_only_full_cuda_12_8_driver_not_met", True, False),
        ("570.65", "full_cuda_12_8_ga_driver_compatible", True, True),
        ("572.61", "full_cuda_12_8_ga_driver_compatible", True, True),
    ],
)
def test_cuda_12_8_driver_compatibility_reports_windows_driver_floors(
    driver, status, minor_compatible, full_12_8
):
    report = diagnostic._cuda_12_8_driver_compatibility([{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": driver,
    }])
    assert report["status"] == status
    assert report["cuda_12x_minor_compatibility"] is minor_compatible
    assert report["cuda_12_8_ga_driver_requirement_met"] is full_12_8
    assert report["torch_cuda_runtime_initialized"] is False


def test_cuda_12_8_driver_compatibility_fails_closed_for_ambiguous_or_unknown_versions():
    ambiguous = diagnostic._cuda_12_8_driver_compatibility([
        {"name": "NVIDIA GeForce GTX 1660 Ti", "driver_version": "570.65"},
        {"name": "NVIDIA GeForce GTX 1660 Ti", "driver_version": "570.65"},
    ])
    unknown = diagnostic._cuda_12_8_driver_compatibility([{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": "32.0.16.1742",
    }])
    assert ambiguous["status"] == "target_gpu_missing_or_ambiguous"
    assert unknown["status"] == "driver_version_unparseable"
    assert ambiguous["cuda_12_8_ga_driver_requirement_met"] is False
    assert unknown["cuda_12_8_ga_driver_requirement_met"] is None


def test_shop_diagnostic_enables_vram_guard_for_both_native_cases(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    calls = []

    def guarded_runner(manifest_path, source, output, *, timeout_seconds, runtime_vram_guard=False):
        assert timeout_seconds == 180
        calls.append(runtime_vram_guard)
        with Image.open(source) as image:
            mode = image.mode
        process = {
            "runtime_vram_guard_enabled": True,
            "runtime_vram_guard_status": "within_budget",
            "runtime_vram_sample_count": 2,
            "runtime_vram_peak_used_mib": 5500.0,
            "runtime_vram_min_free_mib": 644.0,
            "runtime_vram_max_device_used_mib": 5632.0,
            "runtime_vram_reserve_mib": 512,
            "runtime_vram_budget_mib": 6144,
        }
        return {
            "real_inference_verified": True,
            "completed_engine_count": 4,
            "runtime_vram_guard_requested": runtime_vram_guard,
            "runtime_vram_budget_passed": runtime_vram_guard,
            "engines": {
                name: {
                    "status": "native_process_and_2x_output_validated",
                    "size": [256, 192],
                    "mode": mode,
                    "sha256": "b" * 64,
                    "alpha_pixels_match_source": mode == "RGBA",
                    "icc_preserved": True,
                    "dpi_preserved": True,
                    "process": dict(process),
                }
                for name in ENGINES
            },
            "failures": {},
        }

    report = diagnostic.run_diagnostic(
        manifest, tmp_path / "report",
        gpu_probe=_gpu,
        engine_runner=guarded_runner,
        anime4k_probe=lambda _manifest: _anime(),
        manifest_loader=lambda _manifest: {},
    )

    assert calls == [True, True]
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"] is True
    assert report["native_cli_runtime_vram_budget_passed"] is True
    assert all(report["per_engine_native_cli_runtime_vram_budget_passed"].values())
    # The separate bridge case was not run, so total shop acceptance must stay false.
    assert report["runtime_vram_budget_passed"] is False
    assert report["shop_gpu_acceptance_passed"] is False
