"""Local-only GTX 1660 Ti / Vulkan smoke test for the four native V2.1.1 engines.

Uses two generated synthetic PNGs (RGB and RGBA with sRGB ICC + 300 DPI).
It never opens customer artwork, accesses the network, uploads files, or changes
the accepted V2 output. A passing report proves native CLI execution and basic
output invariants only; it does not certify visual quality or print readiness.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageCms, ImageDraw

from signprint_ai.v211_auto_setup import default_manifest, qa_root
from tools.v211_four_engine_real_inference_qa import run as run_real_inference_qa
from tools.v211_four_engine_subprocess import ENGINES


def _parse_nvidia_smi_csv(value: str) -> list[dict]:
    devices = []
    for row in csv.reader(io.StringIO(value)):
        if len(row) < 4:
            continue
        name, driver, total, free = (part.strip() for part in row[:4])
        try:
            total_mib = int(float(total))
            free_mib = int(float(free))
        except (TypeError, ValueError):
            continue
        devices.append({
            "name": name[:160],
            "driver_version": driver[:40],
            "memory_total_mib": total_mib,
            "memory_free_mib": free_mib,
        })
    return devices


def _parse_vulkan_summary(value: str) -> dict:
    devices = []
    api_versions = []
    for line in value.splitlines():
        device = re.search(r"deviceName\s*=\s*(.+)$", line, re.IGNORECASE)
        if device:
            name = device.group(1).strip()
            if name and name not in devices:
                devices.append(name[:160])
        api = re.search(r"apiVersion\s*=\s*(.+)$", line, re.IGNORECASE)
        if api:
            version = api.group(1).strip()
            if version and version not in api_versions:
                api_versions.append(version[:40])
    return {"device_names": devices, "api_versions": api_versions}


def _run_probe(executable: str | None, args: list[str], timeout: int = 15) -> dict:
    if not executable:
        return {"available": False, "success": False, "status": "not_found"}
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"available": True, "success": False, "status": "timeout"}
    except OSError as exc:
        return {
            "available": True,
            "success": False,
            "status": "launch_error",
            "error_type": type(exc).__name__,
        }
    return {
        "available": True,
        "success": completed.returncode == 0,
        "status": "ok" if completed.returncode == 0 else "nonzero_exit",
        "return_code": int(completed.returncode),
        "stdout": completed.stdout or "",
    }


def _find_tool(name: str) -> str | None:
    found = shutil.which(name) or shutil.which(name + ".exe")
    if found:
        return found
    if os.name == "nt":
        if name == "nvidia-smi":
            roots = [
                Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
                Path(os.environ.get("SystemRoot", "C:/Windows"))
                / "System32" / "nvidia-smi.exe",
            ]
        elif name == "vulkaninfo":
            sdk = os.environ.get("VULKAN_SDK")
            roots = [Path(sdk) / "Bin" / "vulkaninfo.exe"] if sdk else []
        else:
            roots = []
        for candidate in roots:
            if candidate.is_file():
                return str(candidate)
    return None


def _probe_vulkan_loader() -> bool:
    """Check whether the platform Vulkan loader can be loaded."""
    try:
        if os.name == "nt":
            ctypes.WinDLL("vulkan-1.dll")
        elif os.name == "posix":
            ctypes.CDLL("libvulkan.so.1")
        else:
            return False
        return True
    except (AttributeError, OSError):
        return False


def probe_gpu() -> dict:
    """Collect only GPU names, driver, VRAM and Vulkan loader/device identifiers."""
    nvidia_exe = _find_tool("nvidia-smi")
    nvidia = _run_probe(
        nvidia_exe,
        [
            "--query-gpu=name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
    )
    gpus = _parse_nvidia_smi_csv(nvidia.pop("stdout", ""))
    nvidia["devices"] = gpus

    vulkan_loader_available = _probe_vulkan_loader()
    vulkan_exe = _find_tool("vulkaninfo")
    vulkan = _run_probe(vulkan_exe, ["--summary"])
    summary = _parse_vulkan_summary(vulkan.pop("stdout", ""))
    vulkan.update(summary)

    target_nvidia = any("gtx 1660 ti" in item["name"].lower() for item in gpus)
    target_vulkan = any("gtx 1660 ti" in name.lower() for name in summary["device_names"])
    return {
        "nvidia_smi": nvidia,
        "vulkaninfo": vulkan,
        "gtx_1660_ti_detected_by_nvidia_smi": target_nvidia,
        "gtx_1660_ti_detected_by_vulkan": target_vulkan,
        "vulkan_loader_available": vulkan_loader_available,
        "vulkaninfo_succeeded": bool(vulkan.get("success")),
        "vram_budget_6gb_detected": any(
            item["memory_total_mib"] >= 5500 for item in gpus
            if "gtx 1660 ti" in item["name"].lower()
        ),
    }


def create_synthetic_png(path: Path, *, rgba: bool) -> None:
    """Create harmless gradient/edge test artwork with print metadata."""
    width, height = 128, 96
    mode = "RGBA" if rgba else "RGB"
    background = (0, 0, 0, 0) if rgba else (18, 74, 46)
    image = Image.new(mode, (width, height), background)
    draw = ImageDraw.Draw(image)
    for x in range(width):
        color = (20, 70 + x, 45 + x // 2, 255) if rgba else (20, 70 + x, 45 + x // 2)
        draw.line((x, 0, x, 42), fill=color)
    if rgba:
        draw.rectangle((9, 49, 94, 83), fill=(235, 24, 36, 255))
        draw.ellipse((42, 54, 116, 91), fill=(25, 75, 230, 160))
        draw.line((7, 46, 120, 46), fill=(250, 246, 230, 255), width=3)
    else:
        draw.rectangle((9, 49, 94, 83), fill=(235, 24, 36))
        draw.ellipse((42, 54, 116, 91), fill=(25, 75, 230))
        draw.line((7, 46, 120, 46), fill=(250, 246, 230), width=3)
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    image.save(path, format="PNG", dpi=(300, 300), icc_profile=profile)


def _read_local_report(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _case_summary(value: dict) -> dict:
    engine_data = value.get("engines") or {}
    failures = value.get("failures") or {}
    engines = {}
    for name in ENGINES:
        item = engine_data.get(name) or {}
        failure = failures.get(name) or {}
        engines[name] = {
            "status": item.get("status", "failed"),
            "output_size": item.get("size"),
            "mode": item.get("mode"),
            "sha256": item.get("sha256"),
            "alpha_pixels_match_source": item.get("alpha_pixels_match_source", False),
            "icc_preserved": item.get("icc_preserved", False),
            "dpi_preserved": item.get("dpi_preserved", False),
            "error_type": failure.get("error_type"),
            "error_class": failure.get("error_class"),
        }
    return {
        "native_cli_outputs_validated": bool(
            value.get("real_inference_verified")
            and value.get("completed_engine_count") == len(ENGINES)
        ),
        "completed_engine_count": int(value.get("completed_engine_count") or 0),
        "failed_stage": value.get("failed_stage"),
        "failure_type": value.get("failure_type"),
        "engines": engines,
    }


def run_diagnostic(
    manifest: Path,
    output_dir: Path,
    *,
    gpu_probe=probe_gpu,
    engine_runner=run_real_inference_qa,
    timeout_seconds: int = 180,
) -> dict:
    """Run all four verified native CLIs on RGB and RGBA synthetic images."""
    manifest = Path(manifest)
    output_dir = Path(output_dir)
    if not 1 <= int(timeout_seconds) <= 1800:
        raise ValueError("timeout_seconds must be between 1 and 1800")
    output_dir.mkdir(parents=True, exist_ok=True)

    gpu = gpu_probe()
    cases = {}
    with tempfile.TemporaryDirectory(prefix="v211-shop-gpu-", dir=output_dir) as temporary:
        work_root = Path(temporary)
        for case_name, rgba in (("rgb_icc_dpi", False), ("rgba_alpha_icc_dpi", True)):
            source = work_root / (case_name + "-synthetic.png")
            case_output = work_root / case_name
            create_synthetic_png(source, rgba=rgba)
            try:
                result = engine_runner(
                    manifest, source, case_output, timeout_seconds=timeout_seconds
                )
            except Exception as exc:
                result = _read_local_report(case_output / "real_inference_report.json")
                if not result:
                    result = {
                        "real_inference_verified": False,
                        "completed_engine_count": 0,
                        "failed_stage": "execution",
                        "failure_type": type(exc).__name__,
                        "engines": {},
                    }
            cases[case_name] = _case_summary(result)

    engine_matrix = {
        name: {
            "rgb_pass": cases["rgb_icc_dpi"]["engines"][name]["status"]
            == "binary_executed_and_2x_output_validated",
            "rgba_pass": cases["rgba_alpha_icc_dpi"]["engines"][name]["status"]
            == "binary_executed_and_2x_output_validated",
        }
        for name in ENGINES
    }
    for item in engine_matrix.values():
        item["both_cases_pass"] = item["rgb_pass"] and item["rgba_pass"]

    manifest_preflight_passed = bool(
        manifest.is_file()
        and all(case.get("failed_stage") != "manifest_preflight" for case in cases.values())
    )
    all_four = manifest_preflight_passed and all(
        item["both_cases_pass"] for item in engine_matrix.values()
    )
    # A Vulkan loader DLL alone does not prove that the target adapter is
    # visible to Vulkan. Require the GTX 1660 Ti to appear in both NVIDIA-SMI
    # and vulkaninfo, a successful vulkaninfo probe, the loader, and the
    # expected approximately 6 GiB VRAM budget before labeling this a shop GPU.
    gpu_ready = bool(
        gpu.get("gtx_1660_ti_detected_by_nvidia_smi")
        and gpu.get("gtx_1660_ti_detected_by_vulkan")
        and gpu.get("vulkan_loader_available")
        and gpu.get("vulkaninfo_succeeded")
        and gpu.get("vram_budget_6gb_detected")
    )
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_present": manifest.is_file(),
        "manifest_preflight_passed": manifest_preflight_passed,
        "gpu": gpu,
        "engine_matrix": engine_matrix,
        "cases": cases,
        "all_four_native_cli_outputs_validated_on_both_synthetic_cases": all_four,
        "gtx_1660_ti_and_vulkan_environment_detected": gpu_ready,
        "four_engine_cli_passed_on_gtx1660ti_vulkan_host": bool(all_four and gpu_ready),
        "quality_improvement_verified": False,
        "visual_quality_certified": False,
        "print_quality_certified": False,
        "customer_artwork_used": False,
        "network_accessed": False,
        "uploads_performed": False,
        "images_retained": False,
        "notes": [
            "Only generated synthetic RGB/RGBA PNGs were processed.",
            "The report verifies native CLI execution, output dimensions, alpha, ICC and DPI only.",
            "It does not prove visual improvement, face identity, CMYK/RIP quality or print acceptance.",
            "Shop GPU readiness requires GTX 1660 Ti visibility in both NVIDIA-SMI and vulkaninfo, successful vulkaninfo, the Vulkan loader, and the expected 6 GiB VRAM budget; this still does not prove which adapter each CLI selected.",
        ],
    }
    report_path = output_dir / "shop_gpu_diagnostic.json"
    temporary_report = report_path.with_suffix(".json.tmp")
    temporary_report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary_report, report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run local synthetic-only QA for the four NiyomSilp V2.1.1 engines."
    )
    parser.add_argument("--manifest", type=Path, default=default_manifest())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    if args.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = qa_root() / "diagnostics" / stamp
    else:
        output_dir = args.output_dir
    report = run_diagnostic(
        args.manifest, output_dir, timeout_seconds=args.timeout_seconds
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Report saved: " + str(output_dir / "shop_gpu_diagnostic.json"))
    return 0 if report["all_four_native_cli_outputs_validated_on_both_synthetic_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
