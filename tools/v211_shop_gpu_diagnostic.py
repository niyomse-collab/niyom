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
import hashlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import sys
import tempfile

from PIL import Image, ImageCms, ImageDraw

from signprint_ai.v211_auto_setup import default_manifest, qa_root
from tools.v211_four_engine_real_inference_qa import run as run_real_inference_qa
from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_real_engine_manifest import load_real_engine_manifest
from tools.v211_gpu_device_binding import GPUDeviceBindingError, write_bound_manifest

# Real-ESRGAN, Waifu2x and Real-CUGAN are NCNN/Vulkan engines.
# Anime4KCPP v3 has a separate CPU/OpenCL/CUDA processor model.
NCNN_VULKAN_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")


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


def _decode_vulkan_device_properties(raw: bytes, index: int) -> dict:
    """Decode the stable leading fields of VkPhysicalDeviceProperties.

    Vulkan defines five uint32 fields followed by deviceName[256]. Reading only
    this prefix avoids requiring the Vulkan SDK or a third-party Python binding.
    """
    if len(raw) < 276:
        raise ValueError("VkPhysicalDeviceProperties buffer is too small")
    api_version, driver_version, vendor_id, device_id, device_type = struct.unpack_from(
        "<IIIII", raw, 0
    )
    name = raw[20:276].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
    if not name:
        raise ValueError("Vulkan physical device has no name")
    return {
        "index": int(index),
        "name": name[:160],
        "api_version_raw": int(api_version),
        "driver_version_raw": int(driver_version),
        "vendor_id": int(vendor_id),
        "device_id": int(device_id),
        "device_type": int(device_type),
    }


def _enumerate_vulkan_devices_native() -> dict:
    """Enumerate Vulkan physical devices through the installed loader.

    This works without the optional Vulkan SDK/vulkaninfo utility. The returned
    index follows vkEnumeratePhysicalDevices order, the index consumed by NCNN -g.
    """
    try:
        if os.name == "nt":
            library = ctypes.WinDLL("vulkan-1.dll")
        elif os.name == "posix":
            library = ctypes.CDLL("libvulkan.so.1")
        else:
            return {"available": False, "success": False, "status": "unsupported_platform"}
    except OSError:
        return {"available": False, "success": False, "status": "loader_not_found"}

    class VkApplicationInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("pApplicationName", ctypes.c_char_p),
            ("applicationVersion", ctypes.c_uint32),
            ("pEngineName", ctypes.c_char_p),
            ("engineVersion", ctypes.c_uint32),
            ("apiVersion", ctypes.c_uint32),
        ]

    class VkInstanceCreateInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("flags", ctypes.c_uint32),
            ("pApplicationInfo", ctypes.POINTER(VkApplicationInfo)),
            ("enabledLayerCount", ctypes.c_uint32),
            ("ppEnabledLayerNames", ctypes.POINTER(ctypes.c_char_p)),
            ("enabledExtensionCount", ctypes.c_uint32),
            ("ppEnabledExtensionNames", ctypes.POINTER(ctypes.c_char_p)),
        ]

    instance = ctypes.c_void_p()
    created = False
    try:
        create_instance = library.vkCreateInstance
        create_instance.argtypes = [
            ctypes.POINTER(VkInstanceCreateInfo), ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        create_instance.restype = ctypes.c_int32
        enumerate_devices = library.vkEnumeratePhysicalDevices
        enumerate_devices.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        enumerate_devices.restype = ctypes.c_int32
        get_properties = library.vkGetPhysicalDeviceProperties
        get_properties.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        get_properties.restype = None
        destroy_instance = library.vkDestroyInstance
        destroy_instance.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        destroy_instance.restype = None

        app = VkApplicationInfo(
            0, None, b"NiyomSilp V2.1.1 GPU QA", 1,
            b"NiyomSilp", 1, (1 << 22),
        )
        create_info = VkInstanceCreateInfo(
            1, None, 0, ctypes.pointer(app), 0, None, 0, None
        )
        result = int(create_instance(ctypes.byref(create_info), None, ctypes.byref(instance)))
        if result != 0:
            return {
                "available": True, "success": False,
                "status": "vkCreateInstance_failed", "vk_result": result,
            }
        created = True

        count = ctypes.c_uint32(0)
        result = int(enumerate_devices(instance, ctypes.byref(count), None))
        if result != 0:
            return {
                "available": True, "success": False,
                "status": "vkEnumeratePhysicalDevices_failed", "vk_result": result,
            }
        if count.value == 0:
            return {
                "available": True, "success": False,
                "status": "no_vulkan_physical_devices", "device_inventory": [],
            }

        handles = (ctypes.c_void_p * count.value)()
        result = int(enumerate_devices(instance, ctypes.byref(count), handles))
        if result != 0:
            return {
                "available": True, "success": False,
                "status": "vkEnumeratePhysicalDevices_failed", "vk_result": result,
            }

        inventory = []
        for index in range(count.value):
            properties = ctypes.create_string_buffer(1024)
            get_properties(handles[index], ctypes.byref(properties))
            inventory.append(_decode_vulkan_device_properties(properties.raw, index))
        return {
            "available": True,
            "success": bool(inventory),
            "status": "ok" if inventory else "no_vulkan_physical_devices",
            "source": "vulkan_loader_native",
            "device_inventory": inventory,
            "device_names": [item["name"] for item in inventory],
        }
    except (AttributeError, OSError, TypeError, ValueError, struct.error) as exc:
        return {
            "available": True,
            "success": False,
            "status": "native_enumeration_error",
            "error_type": type(exc).__name__,
        }
    finally:
        if created and instance.value:
            try:
                destroy_instance(instance, None)
            except Exception:
                pass


def _parse_vulkan_summary(value: str) -> dict:
    inventory = []
    api_versions = []
    current_index = None
    fallback_index = 0
    for line in value.splitlines():
        gpu = re.search(r"^\s*GPU(\d+)\s*:", line, re.IGNORECASE)
        if gpu:
            current_index = int(gpu.group(1))
        device = re.search(r"deviceName\s*=\s*(.+)$", line, re.IGNORECASE)
        if device:
            name = device.group(1).strip()
            index = fallback_index if current_index is None else current_index
            if name and not any(
                item["index"] == index and item["name"] == name for item in inventory
            ):
                inventory.append({"index": index, "name": name[:160]})
                fallback_index += 1
        api = re.search(r"apiVersion\s*=\s*(.+)$", line, re.IGNORECASE)
        if api:
            version = api.group(1).strip()
            if version and version not in api_versions:
                api_versions.append(version[:40])
    return {
        "device_inventory": inventory,
        "device_names": [item["name"] for item in inventory],
        "api_versions": api_versions,
    }


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
        "stderr": completed.stderr or "",
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


def probe_nvidia_smi_memory() -> dict:
    """Read only NVIDIA-SMI VRAM data before each native process.

    Avoids repeating Vulkan loader and Anime4KCPP device enumeration per tile.
    """
    executable = _find_tool("nvidia-smi")
    report = _run_probe(
        executable,
        [
            "--query-gpu=name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
    )
    devices = _parse_nvidia_smi_csv(report.pop("stdout", ""))
    report.pop("stderr", None)
    report["devices"] = devices
    return {"nvidia_smi": report}


def _parse_anime4k_device_inventory(value: str) -> dict:
    """Parse the official Anime4KCPP -l output by processor section."""
    inventory = {}
    current = None
    for line in value.splitlines():
        section = re.match(r"^\s*(CPU|OpenCL|CUDA)\s*:\s*$", line, re.IGNORECASE)
        if section:
            current = section.group(1).lower()
            inventory.setdefault(current, [])
            continue
        entry = re.match(r"^\s*\[(\d+)\]\s+(.+)$", line)
        if entry and current:
            raw_name = entry.group(2).strip()
            name = raw_name.split(" (", 1)[0].strip()
            if name:
                inventory.setdefault(current, []).append({
                    "index": int(entry.group(1)),
                    "name": name[:160],
                })
    return inventory


def probe_anime4k_backend(manifest: Path) -> dict:
    """Inventory Anime4KCPP only after the complete four-engine manifest passes SHA/provenance checks.

    Anime4KCPP v3 exposes --lp (processor list) and -l (device list).
    Never execute a path read from an unverified manifest, even for a harmless
    capability probe. Inventory is not proof of the backend used by inference.
    """
    try:
        # This verifies all four isolated engine roots, official archive pins,
        # executable hashes, individual model-asset hashes and exact CLI
        # contracts before any manifest-supplied native binary is launched.
        commands = load_real_engine_manifest(Path(manifest))
        command = commands.get("anime4k")
        argv = tuple(command.argv) if command is not None else ()
        if not argv:
            return {
                "status": "manifest_preflight_failed",
                "error_type": "ValueError",
            }
        executable = Path(argv[0])
        args = list(argv[1:])
        if not executable.is_absolute() or not executable.is_file():
            return {
                "status": "manifest_preflight_failed",
                "error_type": "FileNotFoundError",
            }

        def option_value(short: str, long: str, default):
            for index, item in enumerate(args[:-1]):
                if item in (short, long):
                    return args[index + 1]
            return default

        processors = _run_probe(str(executable), ["--lp"])
        devices = _run_probe(str(executable), ["-l"])
        processor_text = (processors.get("stdout", "") + "\n" +
                          processors.get("stderr", ""))[:8000]
        device_text = (devices.get("stdout", "") + "\n" +
                       devices.get("stderr", ""))[:8000]
        available_processors = [
            name for name in ("cpu", "opencl", "cuda")
            if re.search(r"\b" + name + r"\b", processor_text, re.IGNORECASE)
        ]
        device_inventory_by_processor = _parse_anime4k_device_inventory(device_text)
        recommended_gpu = None
        for backend in ("cuda", "opencl"):
            if backend not in available_processors:
                continue
            matching = [
                item for item in device_inventory_by_processor.get(backend, [])
                if "gtx 1660 ti" in item["name"].lower()
            ]
            if len(matching) == 1:
                recommended_gpu = {
                    "processor": backend,
                    "device_index": matching[0]["index"],
                    "device_name": matching[0]["name"],
                }
                break
        return {
            "status": "ok" if processors.get("success") and devices.get("success")
                      else "partial_or_failed",
            "manifest_preflight_passed": True,
            "executable_name": executable.name,
            "processor_probe": {
                "available": bool(processors.get("available")),
                "success": bool(processors.get("success")),
                "status": processors.get("status"),
                "return_code": processors.get("return_code"),
                "output": processor_text,
            },
            "device_probe": {
                "available": bool(devices.get("available")),
                "success": bool(devices.get("success")),
                "status": devices.get("status"),
                "return_code": devices.get("return_code"),
                "output": device_text,
            },
            "available_processors": available_processors,
            "device_inventory_by_processor": device_inventory_by_processor,
            "recommended_gpu_processor_device": recommended_gpu,
            "gtx_1660_ti_visible_in_device_inventory":
                "gtx 1660 ti" in device_text.lower(),
            "configured_processor": option_value("-p", "--processor", "auto"),
            "configured_device": option_value("-d", "--device", 0),
            "processor_selection_verified": False,
            "device_selection_verified": False,
            "note": (
                "Anime4KCPP uses CPU/OpenCL/CUDA processors, not NCNN Vulkan. "
                "This is a capability inventory only; configured processor/device "
                "values are reported above but do not prove which backend/device "
                "performed the image inference."
            ),
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {
            "status": "manifest_preflight_failed",
            "error_type": type(exc).__name__,
        }


def probe_gpu() -> dict:
    """Collect GPU names, driver, VRAM and indexed Vulkan physical devices.

    vulkaninfo is optional. If the SDK utility is absent, enumerate devices
    directly through vulkan-1.dll/libvulkan so end-user PCs need no SDK install.
    """
    nvidia_exe = _find_tool("nvidia-smi")
    nvidia = _run_probe(
        nvidia_exe,
        [
            "--query-gpu=name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
    )
    gpus = _parse_nvidia_smi_csv(nvidia.pop("stdout", ""))
    nvidia.pop("stderr", None)
    nvidia["devices"] = gpus

    vulkan_loader_available = _probe_vulkan_loader()
    vulkan_exe = _find_tool("vulkaninfo")
    vulkan = _run_probe(vulkan_exe, ["--summary"])
    summary = _parse_vulkan_summary(vulkan.pop("stdout", ""))
    vulkan.pop("stderr", None)
    # Keep the CLI result truthful: native loader enumeration is not a
    # successful execution of the separate vulkaninfo utility.
    vulkaninfo_succeeded = bool(vulkan.get("success") and summary["device_inventory"])
    inventory_source = "vulkaninfo" if vulkaninfo_succeeded else None
    native_enumeration = None
    if not vulkaninfo_succeeded:
        # Ignore partial stdout from a failed CLI and use only a successful
        # native-loader enumeration as the fallback source.
        summary = {"device_inventory": [], "device_names": [], "api_versions": []}
        native = _enumerate_vulkan_devices_native()
        if native.get("success"):
            summary = {
                "device_inventory": native.get("device_inventory", []),
                "device_names": native.get("device_names", []),
                "api_versions": [],
            }
            inventory_source = "vulkan_loader_native"
            native_enumeration = {
                "success": True,
                "status": native.get("status", "ok"),
                "source": "vulkan_loader_native",
                "device_count": len(summary["device_inventory"]),
            }
        else:
            native_enumeration = {
                "success": False,
                "status": native.get("status", "unavailable"),
                "vk_result": native.get("vk_result"),
                "error_type": native.get("error_type"),
            }
    vulkan.update(summary)
    vulkan["inventory_source"] = inventory_source
    if native_enumeration is not None:
        vulkan["native_enumeration"] = native_enumeration

    target_nvidia = any("gtx 1660 ti" in item["name"].lower() for item in gpus)
    target_vulkan_devices = [
        item for item in summary["device_inventory"]
        if "gtx 1660 ti" in item["name"].lower()
    ]
    target_vulkan = bool(target_vulkan_devices)
    return {
        "nvidia_smi": nvidia,
        "vulkaninfo": vulkan,
        "vulkan_device_inventory": summary["device_inventory"],
        "vulkan_device_index": (
            target_vulkan_devices[0]["index"] if len(target_vulkan_devices) == 1 else None
        ),
        "vulkan_target_device_match_count": len(target_vulkan_devices),
        "gtx_1660_ti_detected_by_nvidia_smi": target_nvidia,
        "gtx_1660_ti_detected_by_vulkan": target_vulkan,
        "vulkan_loader_available": vulkan_loader_available,
        "vulkaninfo_succeeded": vulkaninfo_succeeded,
        "vulkan_device_inventory_succeeded": bool(summary["device_inventory"]),
        "vulkan_inventory_source": inventory_source,
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


def _runtime_device_evidence_verified(flag: object, telemetry: object) -> bool:
    """Validate the evidence fields instead of trusting a single PASS boolean."""
    if flag is not True or not isinstance(telemetry, dict):
        return False
    process_count = telemetry.get("runtime_device_process_count")
    verified_count = telemetry.get("runtime_device_verified_process_count")
    sample_count = telemetry.get("runtime_device_sample_count")
    adapter_index = telemetry.get("runtime_adapter_index")
    adapter_name = telemetry.get("runtime_adapter_name")
    backend_apis = telemetry.get("runtime_adapter_backend_apis")
    return bool(
        telemetry.get("runtime_device_all_processes_verified") is True
        and telemetry.get("runtime_device_probe_conflict") is False
        and telemetry.get("runtime_device_probe_status") == "verified"
        and isinstance(process_count, int) and not isinstance(process_count, bool)
        and process_count >= 1
        and isinstance(verified_count, int) and not isinstance(verified_count, bool)
        and verified_count == process_count
        and isinstance(sample_count, int) and not isinstance(sample_count, bool)
        and sample_count >= process_count
        and isinstance(adapter_index, int) and not isinstance(adapter_index, bool)
        and adapter_index >= 0
        and isinstance(adapter_name, str)
        and "gtx 1660 ti" in adapter_name.casefold()
        and isinstance(backend_apis, list) and bool(backend_apis)
        and all(item in ("graphics", "compute") for item in backend_apis)
    )


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
            "runtime_device_use_verified": _runtime_device_evidence_verified(
                item.get("runtime_device_use_verified"),
                item.get("runtime_device_telemetry"),
            ),
            "runtime_device_telemetry": (
                item.get("runtime_device_telemetry")
                if isinstance(item.get("runtime_device_telemetry"), dict) else {}
            ),
            "error_type": failure.get("error_type"),
            "error_class": failure.get("error_class"),
        }
    return {
        "native_cli_outputs_validated": bool(
            value.get("real_inference_verified")
            and value.get("completed_engine_count") == len(ENGINES)
        ),
        "completed_engine_count": int(value.get("completed_engine_count") or 0),
        "runtime_device_use_verified": {
            name: bool(engines[name]["runtime_device_use_verified"])
            for name in ENGINES
        },
        "failed_stage": value.get("failed_stage"),
        "failure_type": value.get("failure_type"),
        "engines": engines,
    }



def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_synthetic_v2_reference(source: Path, destination: Path) -> None:
    """Create a 2x synthetic accepted-V2 reference with identical metadata."""
    with Image.open(source) as image:
        image.load()
        metadata = {
            key: image.info[key]
            for key in ("icc_profile", "dpi")
            if key in image.info
        }
        scaled = image.resize(
            (image.width * 2, image.height * 2),
            Image.Resampling.LANCZOS,
        )
        try:
            scaled.save(destination, format="PNG", **metadata)
        finally:
            scaled.close()


def _dpi_equal(left, right) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return (
            len(left) == len(right)
            and all(abs(float(a) - float(b)) <= 0.1 for a, b in zip(left, right))
        )
    except (TypeError, ValueError):
        return False


def _run_bridge_integration_case(
    manifest: Path,
    work_root: Path,
    integration_runner,
    *,
    timeout_seconds: int,
) -> dict:
    """Exercise the real bridge + four-engine fusion on synthetic RGBA only.

    The accepted-V2 reference is synthetic and private. The function records
    only booleans/counts; all temporary images, candidates and manifests are
    removed before returning.
    """
    source = Path(work_root) / "bridge-rgba-source.png"
    baseline = Path(work_root) / "bridge-rgba-v2-reference.png"
    create_synthetic_png(source, rgba=True)
    _create_synthetic_v2_reference(source, baseline)
    source_hash_before = _file_sha256(source)
    baseline_hash_before = _file_sha256(baseline)

    try:
        manifest_data = json.loads(Path(manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest_data, dict) or set(manifest_data) != set(ENGINES):
            raise ValueError("manifest must contain exactly four engines")
        for name in ENGINES:
            item = manifest_data[name]
            if not isinstance(item, dict):
                raise ValueError("invalid engine manifest entry")
            current_timeout = item.get("timeout_seconds", 1800)
            if (
                isinstance(current_timeout, bool)
                or not isinstance(current_timeout, int)
                or not 1 <= current_timeout <= 1800
            ):
                raise ValueError("invalid engine timeout in manifest")
            item["timeout_seconds"] = min(current_timeout, int(timeout_seconds))
        bounded_manifest = Path(work_root) / "bridge-integration-manifest.json"
        bounded_manifest.write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        return {
            "case": "rgba_alpha_icc_dpi",
            "status": "manifest_preflight_failed",
            "error_type": type(exc).__name__,
            "passed": False,
            "quality_certified": False,
            "images_retained": False,
        }

    environment_keys = (
        "NIYOMSIL_V211_FOUR_AI",
        "NIYOMSIL_V211_FOUR_AI_MANIFEST",
        "NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR",
    )
    previous_environment = {key: os.environ.get(key) for key in environment_keys}
    with tempfile.TemporaryDirectory(
        prefix="v211-bridge-evidence-", dir=str(Path(work_root).resolve())
    ) as evidence_name:
        evidence_root = Path(evidence_name).resolve()
        os.environ["NIYOMSIL_V211_FOUR_AI"] = "1"
        os.environ["NIYOMSIL_V211_FOUR_AI_MANIFEST"] = str(bounded_manifest.resolve())
        os.environ["NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR"] = str(evidence_root)
        try:
            result = integration_runner(
                source.resolve(),
                baseline.resolve(),
                use_ai=True,
                resize_mode="stretch",
            )
            if not isinstance(result, dict):
                result = {"status": "invalid_bridge_result"}
        except Exception as exc:
            result = {
                "status": "bridge_execution_failed",
                "error_type": type(exc).__name__,
            }
        finally:
            for key, value in previous_environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        output_valid = False
        metadata_checks = {
            "png": False,
            "dimensions": False,
            "colour_mode": False,
            "icc": False,
            "dpi": False,
            "alpha": False,
        }
        output_value = result.get("four_engine_fusion_output")
        if output_value:
            try:
                output_path = Path(output_value).resolve(strict=True)
                output_path.relative_to(evidence_root)
                with Image.open(baseline) as reference, Image.open(output_path) as fused:
                    reference.load()
                    fused.load()
                    metadata_checks["png"] = fused.format == "PNG"
                    metadata_checks["dimensions"] = fused.size == reference.size
                    metadata_checks["colour_mode"] = fused.mode == reference.mode
                    metadata_checks["icc"] = (
                        fused.info.get("icc_profile") == reference.info.get("icc_profile")
                    )
                    metadata_checks["dpi"] = _dpi_equal(
                        fused.info.get("dpi"), reference.info.get("dpi")
                    )
                    if reference.mode == "RGBA" and fused.mode == "RGBA":
                        metadata_checks["alpha"] = (
                            fused.getchannel("A").tobytes()
                            == reference.getchannel("A").tobytes()
                        )
                    elif reference.mode == "RGB" and fused.mode == "RGB":
                        metadata_checks["alpha"] = True
                    output_valid = all(metadata_checks.values())
            except (OSError, ValueError, TypeError):
                output_valid = False

        report_path = None
        if output_value:
            try:
                candidate = Path(output_value).resolve(strict=True)
                candidate.relative_to(evidence_root)
                report_path = candidate.parent / "four_engine_report.json"
            except (OSError, ValueError):
                report_path = None
        engine_report = _read_local_report(report_path) if report_path else {}
        execution = engine_report.get("engine_execution") or {}
        prelaunch = {}
        runtime_by_engine = {}
        runtime_process_evidence = {}
        for name in ENGINES:
            process = ((execution.get(name) or {}).get("process") or {})
            runtime_process_evidence[name] = {
                "runtime_device_process_count": process.get("runtime_device_process_count", 0),
                "runtime_device_verified_process_count": process.get("runtime_device_verified_process_count", 0),
                "runtime_device_all_processes_verified": process.get("runtime_device_all_processes_verified") is True,
                "runtime_device_sample_count": process.get("runtime_device_sample_count", 0),
                "runtime_device_probe_status": process.get("runtime_device_probe_status"),
                "runtime_device_probe_conflict": process.get("runtime_device_probe_conflict") is True,
                "runtime_adapter_name": process.get("runtime_adapter_name"),
                "runtime_adapter_index": process.get("runtime_adapter_index"),
                "runtime_adapter_backend_apis": process.get("runtime_adapter_backend_apis", []),
            }
            runtime_by_engine[name] = _runtime_device_evidence_verified(
                process.get("runtime_device_use_verified"),
                runtime_process_evidence[name],
            )
            checks = process.get("pre_launch_vram_checks", 0)
            minimum = process.get("pre_launch_vram_min_free_mib")
            if isinstance(checks, bool) or not isinstance(checks, int) or checks < 0:
                checks = 0
            if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
                minimum = None
            prelaunch[name] = {
                "checks": checks,
                "minimum_free_mib": minimum,
                "passed": checks >= 1 and minimum is not None and minimum >= 2048,
            }

        effects_raw = result.get("engine_pixel_effect_verified")
        effects = {
            name: bool(isinstance(effects_raw, dict) and effects_raw.get(name) is True)
            for name in ENGINES
        }
        pixels_raw = result.get("engine_pixel_effect_pixels")
        effect_pixels = {}
        for name in ENGINES:
            value = pixels_raw.get(name) if isinstance(pixels_raw, dict) else None
            effect_pixels[name] = (
                value if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                else None
            )
        binding = result.get("device_binding") or {}
        if not isinstance(binding, dict):
            binding = {}
        binding_configured = binding.get("binding_configured") is True
        try:
            source_unchanged = _file_sha256(source) == source_hash_before
        except OSError:
            source_unchanged = False
        try:
            baseline_unchanged = _file_sha256(baseline) == baseline_hash_before
        except OSError:
            baseline_unchanged = False
        all_prelaunch_passed = all(item["passed"] for item in prelaunch.values())
        all_effects_verified = all(effects.values())
        completed_count = result.get("completed_engine_count", 0)
        if isinstance(completed_count, bool) or not isinstance(completed_count, int):
            completed_count = 0
        fusion_passed = bool(
            result.get("status") == "four_engine_fusion_preview_ready"
            and completed_count == len(ENGINES)
            and result.get("fusion_implemented") is True
            and result.get("all_four_engine_pixels_contributed") is True
            and all_effects_verified
            and output_valid
            and source_unchanged
            and baseline_unchanged
            and binding_configured
            and all_prelaunch_passed
        )
        runtime_verified = all(runtime_by_engine.values())
        return {
            "case": "rgba_alpha_icc_dpi",
            "status": str(result.get("status") or "unknown")[:80],
            "passed": fusion_passed,
            "completed_engine_count": completed_count,
            "fusion_implemented": result.get("fusion_implemented") is True,
            "all_four_engine_pixels_contributed": (
                result.get("all_four_engine_pixels_contributed") is True
            ),
            "engine_pixel_effect_verified": effects,
            "engine_pixel_effect_pixels": effect_pixels,
            "output_metadata": metadata_checks,
            "source_unchanged": source_unchanged,
            "v2_baseline_unchanged": baseline_unchanged,
            "device_binding_configured": binding_configured,
            "pre_launch_vram": prelaunch,
            "pre_launch_vram_checks_passed": all_prelaunch_passed,
            "runtime_device_use_verified": runtime_verified,
            "per_engine_runtime_device_use_verified": runtime_by_engine,
            "runtime_process_evidence": runtime_process_evidence,
            "quality_certified": False,
            "print_quality_certified": False,
            "customer_artwork_used": False,
            "network_accessed": False,
            "uploads_performed": False,
            "images_retained": False,
            "error_type": result.get("error_type"),
        }


def run_diagnostic(
    manifest: Path,
    output_dir: Path,
    *,
    gpu_probe=probe_gpu,
    engine_runner=run_real_inference_qa,
    anime4k_probe=probe_anime4k_backend,
    manifest_loader=load_real_engine_manifest,
    timeout_seconds: int = 180,
    bind_devices: bool = True,
    integration_runner=None,
) -> dict:
    """Run all four verified native CLIs on RGB and RGBA synthetic images."""
    manifest = Path(manifest)
    output_dir = Path(output_dir)
    if not 1 <= int(timeout_seconds) <= 1800:
        raise ValueError("timeout_seconds must be between 1 and 1800")
    output_dir.mkdir(parents=True, exist_ok=True)

    gpu = gpu_probe()
    # Verify the complete pinned four-engine manifest independently before
    # trusting an inventory callback or launching any manifest-supplied CLI.
    # This second boundary is intentional: injected/test probes must never be
    # able to turn an invalid or tampered manifest into permission to execute.
    manifest_preflight_error = None
    try:
        manifest_loader(manifest)
    except Exception as exc:
        manifest_preflight_error = exc
        anime4k_backend = {
            "status": "manifest_preflight_failed",
            "manifest_preflight_passed": False,
            "error_type": type(exc).__name__,
        }
    else:
        try:
            anime4k_backend = anime4k_probe(manifest)
        except Exception as exc:
            manifest_preflight_error = exc
            anime4k_backend = {
                "status": "manifest_preflight_failed",
                "manifest_preflight_passed": False,
                "error_type": type(exc).__name__,
            }
    manifest_preflight_ok = bool(
        manifest_preflight_error is None
        and manifest.is_file()
        and anime4k_backend.get("manifest_preflight_passed") is True
    )
    cases = {}
    device_binding = None
    binding_error = None
    with tempfile.TemporaryDirectory(prefix="v211-shop-gpu-", dir=output_dir) as temporary:
        work_root = Path(temporary)
        bound_manifest = Path(manifest)
        if bind_devices and manifest_preflight_ok:
            try:
                device_binding = write_bound_manifest(
                    manifest, work_root / "manifest.runtime-bound.json",
                    gpu, anime4k_backend,
                )
                bound_manifest = work_root / "manifest.runtime-bound.json"
            except GPUDeviceBindingError as exc:
                binding_error = exc
        for case_name, rgba in (("rgb_icc_dpi", False), ("rgba_alpha_icc_dpi", True)):
            source = work_root / (case_name + "-synthetic.png")
            case_output = work_root / case_name
            create_synthetic_png(source, rgba=rgba)
            if not manifest_preflight_ok:
                # Do not call any injected or production engine runner when
                # the pinned manifest has not passed its full preflight.
                result = {
                    "real_inference_verified": False,
                    "completed_engine_count": 0,
                    "failed_stage": "manifest_preflight",
                    "failure_type": (
                        anime4k_backend.get("error_type")
                        or "ManifestPreflightFailed"
                    ),
                    "engines": {},
                }
            elif binding_error is not None:
                result = {
                    "real_inference_verified": False,
                    "completed_engine_count": 0,
                    "failed_stage": "gpu_binding",
                    "failure_type": type(binding_error).__name__,
                    "engines": {},
                }
            else:
                try:
                    result = engine_runner(
                        bound_manifest, source, case_output,
                        timeout_seconds=timeout_seconds,
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

        bridge_integration = {
            "case": "rgba_alpha_icc_dpi",
            "status": "not_run",
            "passed": False,
            "quality_certified": False,
            "images_retained": False,
        }
        if integration_runner is not None:
            if not manifest_preflight_ok:
                bridge_integration = {
                    **bridge_integration,
                    "status": "manifest_preflight_failed",
                }
            elif binding_error is not None or not bind_devices or device_binding is None:
                bridge_integration = {
                    **bridge_integration,
                    "status": "gpu_binding_failed",
                }
            else:
                bridge_integration = _run_bridge_integration_case(
                    manifest, work_root, integration_runner,
                    timeout_seconds=timeout_seconds,
                )

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
        manifest_preflight_ok
        and all(case.get("failed_stage") != "manifest_preflight" for case in cases.values())
    )
    all_four = manifest_preflight_passed and all(
        item["both_cases_pass"] for item in engine_matrix.values()
    )
    ncnn_vulkan_engines_pass = manifest_preflight_passed and all(
        engine_matrix[name]["both_cases_pass"] for name in NCNN_VULKAN_ENGINES
    )
    anime4k_cli_pass = bool(engine_matrix["anime4k"]["both_cases_pass"])
    # A Vulkan loader DLL alone does not prove that the target adapter is
    # visible to Vulkan. Require one unambiguous GTX 1660 Ti physical-device
    # index visible to both NVIDIA-SMI and Vulkan, a successful inventory,
    # the loader, and the expected approximately 6 GiB VRAM budget.
    gpu_ready = bool(
        gpu.get("gtx_1660_ti_detected_by_nvidia_smi")
        and gpu.get("gtx_1660_ti_detected_by_vulkan")
        and gpu.get("vulkan_device_index") is not None
        and gpu.get("vulkan_loader_available")
        and gpu.get("vulkan_device_inventory_succeeded")
        and gpu.get("vram_budget_6gb_detected")
    )
    device_binding_applied = bool(bind_devices and device_binding and binding_error is None)
    bridge_runtime = bridge_integration.get("per_engine_runtime_device_use_verified")
    if not isinstance(bridge_runtime, dict):
        bridge_runtime = {name: False for name in ENGINES}
    else:
        bridge_runtime = {name: bridge_runtime.get(name) is True for name in ENGINES}
    native_runtime = {
        name: all(
            (cases.get(case_name, {}).get("engines", {}).get(name) or {}).get(
                "runtime_device_use_verified"
            ) is True
            for case_name in ("rgb_icc_dpi", "rgba_alpha_icc_dpi")
        )
        for name in ENGINES
    }
    runtime_by_engine = {
        name: bool(native_runtime[name] and bridge_runtime[name])
        for name in ENGINES
    }
    runtime_device_use_verified = all(runtime_by_engine.values())
    engine_backend_expectations = {
        name: {
            "expected_backend": (
                "NCNN Vulkan; explicit -g index when binding is enabled"
                if name in NCNN_VULKAN_ENGINES
                else "Anime4KCPP CUDA/OpenCL; explicit -p/-d when binding is enabled"
            ),
            "device_index_configured": (
                device_binding["ncnn_vulkan"]["device_index"]
                if device_binding and name in NCNN_VULKAN_ENGINES
                else device_binding["anime4k"]["device_index"]
                if device_binding and name == "anime4k"
                else None
            ),
            "target_adapter_selection_verified": runtime_by_engine[name],
        }
        for name in ENGINES
    }
    report = {
        "schema_version": 6,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_present": manifest.is_file(),
        "manifest_preflight_passed": manifest_preflight_passed,
        "gpu": gpu,
        "vulkaninfo_succeeded": bool(gpu.get("vulkaninfo_succeeded")),
        "vulkan_device_inventory_succeeded": bool(gpu.get("vulkan_device_inventory_succeeded")),
        "vulkan_inventory_source": gpu.get("vulkan_inventory_source"),
        "gpu_device_inventory_source": (gpu.get("vulkaninfo") or {}).get("inventory_source"),
        "ncnn_vulkan_target_device_index": gpu.get("vulkan_device_index"),
        "vulkan_target_device_index_unambiguous": gpu.get("vulkan_device_index") is not None,
        "anime4k_backend_inventory": anime4k_backend,
        "anime4k_gpu_recommendation": anime4k_backend.get("recommended_gpu_processor_device"),
        "device_binding": device_binding,
        "device_binding_applied": device_binding_applied,
        "device_binding_block_reason": str(binding_error) if binding_error else None,
        "engine_matrix": engine_matrix,
        "engine_backend_expectations": engine_backend_expectations,
        "per_engine_backend_selection_verified": runtime_by_engine,
        "anime4k_backend_selection_verified": runtime_by_engine["anime4k"],
        "ncnn_vulkan_engine_names": list(NCNN_VULKAN_ENGINES),
        "three_ncnn_vulkan_cli_outputs_validated_on_both_synthetic_cases": ncnn_vulkan_engines_pass,
        "three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host": bool(
            ncnn_vulkan_engines_pass and gpu_ready and device_binding_applied
        ),
        "anime4k_cli_outputs_validated_on_both_synthetic_cases": anime4k_cli_pass,
        "cases": cases,
        "bridge_integration": bridge_integration,
        "runtime_device_use_verified": runtime_device_use_verified,
        "per_engine_runtime_device_use_verified": runtime_by_engine,
        "shop_gpu_acceptance_passed": bool(
            bridge_integration.get("passed")
            and all_four
            and gpu_ready
            and device_binding_applied
            and runtime_device_use_verified
        ),
        "four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host": bool(
            bridge_integration.get("passed")
            and all_four
            and gpu_ready
            and device_binding_applied
        ),
        "all_four_native_cli_outputs_validated_on_both_synthetic_cases": all_four,
        "gtx_1660_ti_and_vulkan_environment_detected": gpu_ready,
        "all_four_cli_validated_on_gtx1660ti_vulkan_equipped_host": bool(
            all_four and gpu_ready and device_binding_applied
        ),
        "four_engine_cli_passed_on_gtx1660ti_vulkan_host": bool(
            all_four and gpu_ready and device_binding_applied
        ),
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
            "Shop GPU readiness requires GTX 1660 Ti visibility in NVIDIA-SMI and Vulkan physical-device inventory (from vulkaninfo or direct loader enumeration), the Vulkan loader, and the expected 6 GiB VRAM budget; this still does not prove which adapter each CLI selected.",
            "When bind_devices is enabled, a private per-run manifest explicitly configures the unique Vulkan index with -g for all three NCNN engines and the unique Anime4KCPP CUDA/OpenCL backend/device with -p/-d. The installed manifest is never modified.",
            "Runtime adapter evidence is sampled from NVML graphics/compute process lists while each native PID is alive; acceptance requires the PID to appear on the unique GTX 1660 Ti with non-zero GPU memory.",
            "If NVML process accounting is unavailable, a process exits before it can be sampled, or the PID is visible only on another adapter, runtime_device_use_verified remains false.",
            "Shop GPU acceptance and a zero CLI exit code require positive runtime-adapter telemetry for all four native processes on the selected GTX 1660 Ti in RGB, RGBA, and end-to-end bridge runs.",
            "The end-to-end bridge case runs the actual V2.1.1 bridge and four-engine fusion on a generated RGBA/ICC/300-DPI image; it checks four pixel contributions, per-process VRAM preflight records, exact V2-reference preservation and output metadata.",
            "A passing bridge case still does not prove which physical adapter each native process used or certify visual/print quality; compare real owner-approved images separately.",
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
    from signprint_ai.v211_four_engine_bridge import maybe_run_four_engine_assist

    report = run_diagnostic(
        args.manifest, output_dir,
        timeout_seconds=args.timeout_seconds,
        integration_runner=maybe_run_four_engine_assist,
    )
    # The frozen installer is a windowed EXE; PyInstaller may set stdout=None.
    # The JSON report is always written to disk, so console output is optional.
    if sys.stdout is not None:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Report saved: " + str(output_dir / "shop_gpu_diagnostic.json"))
    return 0 if report.get("shop_gpu_acceptance_passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
