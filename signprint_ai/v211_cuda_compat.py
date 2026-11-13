"""Read-only CUDA 12.8 driver compatibility hint for the V2.1.1 Windows UI.

This module never imports/initializes PyTorch, changes device selection, touches
Vulkan eligibility, downloads a driver, or starts an inference process.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess


CUDA_12X_MINOR_COMPAT_WINDOWS_MIN = (528, 33, 0)
CUDA_12_8_GA_WINDOWS_MIN = (570, 65, 0)


def parse_nvidia_driver_version(value: object) -> tuple[int, int, int] | None:
    """Parse the dotted version emitted by nvidia-smi, not Device Manager's WDDM tuple."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\\s*(\\d+)\\.(\\d+)(?:\\.(\\d+))?\\s*", value)
    if not match:
        return None
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3) or 0),
    )


def parse_nvidia_smi_devices(value: str) -> list[dict]:
    devices = []
    for row in csv.reader(io.StringIO(value)):
        if len(row) < 2:
            continue
        name, driver = row[0].strip(), row[1].strip()
        if name and driver:
            devices.append({
                "name": name[:160],
                "driver_version": driver[:40],
            })
    return devices


def classify_cuda_12_8_driver_compatibility(devices: list[dict]) -> dict:
    """Classify the GTX 1660 Ti driver floor without claiming CUDA initialized."""
    matches = [
        item for item in devices
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and "gtx 1660 ti" in item["name"].casefold()
    ]
    base = {
        "minimum_windows_driver_cuda_12x_minor_compatibility": "528.33",
        "minimum_windows_driver_cuda_12_8_ga": "570.65",
        "scope": "V2.1.1 bundled PyTorch CUDA 12.8 only; native Vulkan engines are not gated",
        "torch_cuda_runtime_initialized": False,
    }
    if len(matches) != 1:
        return {
            **base,
            "status": "target_gpu_missing_or_ambiguous",
            "driver_version": None,
            "cuda_12x_minor_compatibility": False,
            "cuda_12_8_ga_driver_requirement_met": False,
        }

    raw_version = matches[0].get("driver_version")
    parsed = parse_nvidia_driver_version(raw_version)
    if parsed is None:
        return {
            **base,
            "status": "driver_version_unparseable",
            "driver_version": str(raw_version)[:40] if raw_version is not None else None,
            "cuda_12x_minor_compatibility": None,
            "cuda_12_8_ga_driver_requirement_met": None,
        }

    if parsed < CUDA_12X_MINOR_COMPAT_WINDOWS_MIN:
        status = "below_cuda_12x_minor_compatibility_floor"
        minor_compatible = False
        full_12_8 = False
    elif parsed < CUDA_12_8_GA_WINDOWS_MIN:
        status = "minor_compatibility_only_full_cuda_12_8_driver_not_met"
        minor_compatible = True
        full_12_8 = False
    else:
        status = "full_cuda_12_8_ga_driver_compatible"
        minor_compatible = True
        full_12_8 = True
    return {
        **base,
        "status": status,
        "driver_version": str(raw_version)[:40],
        "cuda_12x_minor_compatibility": minor_compatible,
        "cuda_12_8_ga_driver_requirement_met": full_12_8,
    }


def probe_cuda_12_8_driver_compatibility(*, platform_name: str | None = None, run=None) -> dict:
    """Read nvidia-smi once on Windows; do not invoke CUDA or Vulkan runtimes."""
    current_platform = os.name if platform_name is None else platform_name
    if current_platform != "nt":
        return {
            "status": "not_windows",
            "driver_version": None,
            "torch_cuda_runtime_initialized": False,
        }

    runner = subprocess.run if run is None else run
    try:
        result = runner(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except FileNotFoundError:
        return {
            "status": "nvidia_smi_unavailable",
            "driver_version": None,
            "torch_cuda_runtime_initialized": False,
        }
    except Exception:
        return {
            "status": "driver_probe_failed",
            "driver_version": None,
            "torch_cuda_runtime_initialized": False,
        }

    if getattr(result, "returncode", 1) != 0:
        return {
            "status": "driver_probe_failed",
            "driver_version": None,
            "torch_cuda_runtime_initialized": False,
        }
    return classify_cuda_12_8_driver_compatibility(
        parse_nvidia_smi_devices(getattr(result, "stdout", "") or "")
    )


def format_cuda_driver_status(report: dict) -> tuple[str, str]:
    """Return a concise Thai UI hint and foreground colour."""
    if not isinstance(report, dict):
        return "ตรวจสอบ NVIDIA Driver ไม่สำเร็จ • V2 ยังใช้งานได้ • ตรวจ Vulkan แยก", "#FFB74D"

    status = report.get("status")
    driver = str(report.get("driver_version") or "ไม่ทราบ")
    if status == "not_windows":
        return "", "#B6C0C8"
    if status == "below_cuda_12x_minor_compatibility_floor":
        return (
            f"คำเตือน CUDA: Driver {driver} ต่ำกว่า 528.33 — PyTorch CUDA 12.8 ของ V2/GFPGAN อาจเริ่มไม่ได้; "
            "V2 ยังใช้ได้ และ Native Vulkan AI 4 ตัวไม่ถูกปิดโดยคำเตือนนี้",
            "#FF7777",
        )
    if status == "minor_compatibility_only_full_cuda_12_8_driver_not_met":
        return (
            f"CUDA Driver {driver}: ผ่าน Minor Compatibility (≥528.33) แต่ต่ำกว่า CUDA 12.8 GA (570.65) — "
            "ต้องทดสอบ Torch CUDA จริง; Native Vulkan AI ตรวจแยก",
            "#FFB74D",
        )
    if status == "full_cuda_12_8_ga_driver_compatible":
        return (
            f"CUDA Driver {driver}: ถึงเกณฑ์ CUDA 12.8 GA (≥570.65) — ยังไม่ยืนยัน Torch CUDA runtime; "
            "Native Vulkan AI ตรวจแยก",
            "#86EFAC",
        )
    if status == "target_gpu_missing_or_ambiguous":
        detail = "ไม่พบหรือพบ GTX 1660 Ti มากกว่าหนึ่งตัว"
    elif status == "driver_version_unparseable":
        detail = f"อ่านรุ่น Driver ไม่ได้ ({driver})"
    elif status == "nvidia_smi_unavailable":
        detail = "ไม่พบ nvidia-smi"
    else:
        detail = "เรียกตรวจ nvidia-smi ไม่สำเร็จ"
    return (
        f"CUDA: {detail} — ยังไม่ยืนยัน PyTorch CUDA 12.8; V2 ยังใช้ได้ และ Native Vulkan AI ตรวจแยก",
        "#FFB74D",
    )
