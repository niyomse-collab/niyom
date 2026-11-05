import json
from pathlib import Path

from PIL import Image

from tools import v211_shop_gpu_diagnostic as diagnostic
from tools.v211_four_engine_subprocess import ENGINES


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
        "gtx_1660_ti_detected_by_nvidia_smi": True,
        "gtx_1660_ti_detected_by_vulkan": True,
        "vulkaninfo_succeeded": True,
        "vram_budget_6gb_detected": True,
    }


def _successful_runner(manifest, source, output, *, timeout_seconds):
    assert timeout_seconds == 180
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


def test_vulkan_summary_parser_extracts_device_and_api():
    parsed = diagnostic._parse_vulkan_summary(
        "deviceName = NVIDIA GeForce GTX 1660 Ti\napiVersion = 1.3.0\n"
    )
    assert parsed["device_names"] == ["NVIDIA GeForce GTX 1660 Ti"]
    assert parsed["api_versions"] == ["1.3.0"]


def test_synthetic_pngs_include_rgb_rgba_icc_and_300dpi(tmp_path):
    rgb = tmp_path / "rgb.png"
    rgba = tmp_path / "rgba.png"
    diagnostic.create_synthetic_png(rgb, rgba=False)
    diagnostic.create_synthetic_png(rgba, rgba=True)
    with Image.open(rgb) as image:
        assert image.mode == "RGB"
        assert image.info.get("icc_profile")
        assert image.info["dpi"] == (300.0, 300.0)
    with Image.open(rgba) as image:
        assert image.mode == "RGBA"
        assert image.info.get("icc_profile")
        assert image.info["dpi"] == (300.0, 300.0)
        assert image.getchannel("A").getextrema()[0] == 0


def test_local_diagnostic_runs_all_four_on_both_synthetic_cases(tmp_path):
    report = diagnostic.run_diagnostic(
        tmp_path / "manifest.json", tmp_path / "report",
        gpu_probe=_gpu, engine_runner=_successful_runner,
    )
    assert report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"]
    assert report["gtx_1660_ti_and_vulkan_environment_detected"]
    assert report["four_engine_cli_passed_on_gtx1660ti_vulkan_host"]
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

    report = diagnostic.run_diagnostic(
        tmp_path / "manifest.json", tmp_path / "report",
        gpu_probe=_gpu, engine_runner=one_engine_fails,
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
