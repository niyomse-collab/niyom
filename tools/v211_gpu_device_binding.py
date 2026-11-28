"""Fail-closed runtime GPU binding for the four native V2.1.1 engines.

The three NCNN/Vulkan CLIs receive the unique GTX 1660 Ti Vulkan physical-device
index through -g. Anime4KCPP is independent of Vulkan and receives its own
CUDA/OpenCL processor and device index through -p/-d. Inventory is selection
evidence only; it does not prove which adapter a native process actually used.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.v211_four_engine_subprocess import ENGINES

TARGET_GPU = "gtx 1660 ti"
NCNN_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")
# Conservative launch threshold, not a promise that every tile/model fits.
MIN_FREE_VRAM_MIB = 2048


class GPUDeviceBindingError(RuntimeError):
    """Raised when the requested GPU cannot be selected without ambiguity."""


def _matches_target(value: Any, target_name: str = TARGET_GPU) -> bool:
    return isinstance(value, str) and target_name.casefold() in value.casefold()


def _valid_device_index(value: Any) -> bool:
    """Accept JSON-style non-negative integers, never bool (a Python int subclass)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


_LUID_TEXT_PATTERN = re.compile(r"0x[0-9a-f]{8}_0x[0-9a-f]{8}", re.IGNORECASE)


def _valid_luid_text(value: Any) -> bool:
    return isinstance(value, str) and _LUID_TEXT_PATTERN.fullmatch(value) is not None


def resolve_vulkan_dxgi_adapter(
    gpu_report: dict,
    *,
    target_name: str = TARGET_GPU,
) -> dict:
    """Match one Vulkan physical device to one DXGI adapter by the OS LUID.

    Device-name matching is retained only as a human-readable target filter.
    The actual identity check is VkPhysicalDeviceIDProperties.deviceLUID against
    DXGI_ADAPTER_DESC1.AdapterLuid. Missing/invalid/ambiguous identifiers fail closed.
    """
    if gpu_report.get("vulkan_inventory_source") != "vulkan_loader_native":
        raise GPUDeviceBindingError(
            "native Vulkan loader inventory with deviceLUID is required"
        )
    if gpu_report.get("vulkan_loader_available") is not True:
        raise GPUDeviceBindingError("Vulkan loader is unavailable")
    if gpu_report.get("vulkan_device_inventory_succeeded") is not True:
        raise GPUDeviceBindingError("Vulkan loader physical-device inventory is unavailable")

    vulkan_devices = gpu_report.get("vulkan_device_inventory") or []
    vulkan_matches = [
        item for item in vulkan_devices
        if isinstance(item, dict) and _matches_target(item.get("name"), target_name)
    ]
    if len(vulkan_matches) != 1:
        raise GPUDeviceBindingError(
            "Vulkan must expose exactly one unambiguous " + target_name + " device"
        )
    vulkan = vulkan_matches[0]
    index = vulkan.get("index")
    reported_index = gpu_report.get("vulkan_device_index")
    match_count = gpu_report.get("vulkan_target_device_match_count")
    if (
        not _valid_device_index(index)
        or not _valid_device_index(reported_index)
        or reported_index != index
        or isinstance(match_count, bool)
        or not isinstance(match_count, int)
        or match_count != 1
    ):
        raise GPUDeviceBindingError(
            "Vulkan target physical-device index is missing or ambiguous"
        )

    vendor_id = vulkan.get("vendor_id")
    device_id = vulkan.get("device_id")
    if (
        isinstance(vendor_id, bool) or not isinstance(vendor_id, int)
        or vendor_id != 0x10DE
    ):
        raise GPUDeviceBindingError("Vulkan target device is not an NVIDIA adapter")
    if isinstance(device_id, bool) or not isinstance(device_id, int) or device_id <= 0:
        raise GPUDeviceBindingError("Vulkan target device PCI ID is invalid")
    if vulkan.get("device_luid_valid") is not True:
        raise GPUDeviceBindingError(
            "Vulkan VkPhysicalDeviceIDProperties.deviceLUID is not valid"
        )
    node_mask = vulkan.get("device_node_mask")
    if (
        isinstance(node_mask, bool) or not isinstance(node_mask, int)
        or node_mask <= 0 or (node_mask & (node_mask - 1)) != 0
    ):
        raise GPUDeviceBindingError("Vulkan deviceNodeMask is invalid")
    vulkan_luid = vulkan.get("device_luid_text")
    if not _valid_luid_text(vulkan_luid):
        raise GPUDeviceBindingError("Vulkan deviceLUID format is invalid")
    vulkan_luid = vulkan_luid.casefold()

    dxgi_devices = gpu_report.get("dxgi_adapter_inventory") or []
    dxgi_matches = [
        item for item in dxgi_devices
        if isinstance(item, dict)
        and _matches_target(item.get("description"), target_name)
        and item.get("vendor_id") == 0x10DE
    ]
    if len(dxgi_matches) != 1:
        raise GPUDeviceBindingError(
            "DXGI must expose exactly one unambiguous " + target_name + " adapter"
        )
    dxgi = dxgi_matches[0]
    dxgi_luid = dxgi.get("luid_text")
    if not _valid_luid_text(dxgi_luid):
        raise GPUDeviceBindingError("DXGI AdapterLuid format is invalid")
    dxgi_luid = dxgi_luid.casefold()
    if vulkan_luid != dxgi_luid:
        raise GPUDeviceBindingError(
            "Vulkan deviceLUID does not match the target DXGI AdapterLuid"
        )

    duplicate_luid = [
        item for item in dxgi_devices
        if isinstance(item, dict)
        and isinstance(item.get("luid_text"), str)
        and item["luid_text"].casefold() == dxgi_luid
    ]
    if len(duplicate_luid) != 1:
        raise GPUDeviceBindingError("DXGI AdapterLuid is duplicated or ambiguous")

    dxgi_vendor_id = dxgi.get("vendor_id")
    dxgi_device_id = dxgi.get("device_id")
    if (
        isinstance(dxgi_vendor_id, bool) or not isinstance(dxgi_vendor_id, int)
        or dxgi_vendor_id != vendor_id
        or isinstance(dxgi_device_id, bool) or not isinstance(dxgi_device_id, int)
        or dxgi_device_id != device_id
    ):
        raise GPUDeviceBindingError("Vulkan and DXGI PCI vendor/device IDs do not match")

    return {
        "device_index": index,
        "device_name": str(vulkan.get("name") or "")[:160],
        "device_luid": vulkan_luid,
        "dxgi_adapter_luid": dxgi_luid,
        "dxgi_adapter_description": str(dxgi.get("description") or "")[:160],
        "device_node_mask": node_mask,
        "vendor_id": vendor_id,
        "device_id": device_id,
        "luid_match_verified": True,
    }


def validate_free_vram_report(
    gpu_report: dict,
    *,
    target_name: str = TARGET_GPU,
) -> dict:
    """Validate a fresh NVIDIA-SMI snapshot for exactly one target adapter."""
    nvidia = gpu_report.get("nvidia_smi") or {}
    devices = nvidia.get("devices") or []
    matches = [
        item for item in devices
        if isinstance(item, dict) and _matches_target(item.get("name"), target_name)
    ]
    if nvidia.get("success") is not True or len(matches) != 1:
        raise GPUDeviceBindingError(
            "NVIDIA-SMI must report exactly one " + target_name + " adapter"
        )
    device = matches[0]
    total = device.get("memory_total_mib")
    free = device.get("memory_free_mib")
    if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
        raise GPUDeviceBindingError("NVIDIA-SMI must report a valid total VRAM capacity")
    if isinstance(free, bool) or not isinstance(free, int) or free < 0:
        raise GPUDeviceBindingError("NVIDIA-SMI must report a valid free VRAM reading")
    if free > total:
        raise GPUDeviceBindingError("NVIDIA-SMI free VRAM exceeds the reported total capacity")
    if free < MIN_FREE_VRAM_MIB:
        raise GPUDeviceBindingError(
            f"insufficient free VRAM: {free} MiB available; "
            f"at least {MIN_FREE_VRAM_MIB} MiB required"
        )
    return {
        "total_mib": total,
        "free_mib": free,
        "minimum_free_mib": MIN_FREE_VRAM_MIB,
        "passed": True,
    }


def resolve_device_selection(
    gpu_report: dict,
    anime4k_report: dict,
    *,
    target_name: str = TARGET_GPU,
) -> dict:
    """Resolve unique Vulkan and Anime4K indexes; reject missing/ambiguous devices."""
    nvidia = gpu_report.get("nvidia_smi") or {}
    nvidia_devices = nvidia.get("devices") or []
    nvidia_matches = [
        item for item in nvidia_devices
        if isinstance(item, dict) and _matches_target(item.get("name"), target_name)
    ]
    if nvidia.get("success") is not True or len(nvidia_matches) != 1:
        raise GPUDeviceBindingError(
            "NVIDIA-SMI must report exactly one " + target_name + " adapter"
        )

    # A 6 GB card can be almost full because of Photoshop, browsers or another
    # inference process. Require a fresh NVIDIA-SMI free-memory reading before
    # binding any optional native engine. This is only a launch preflight: VRAM
    # can change afterwards, so native processes must still handle OOM safely.
    nvidia_target = nvidia_matches[0]
    memory_total = nvidia_target.get("memory_total_mib")
    memory_free = nvidia_target.get("memory_free_mib")
    if (
        isinstance(memory_total, bool)
        or not isinstance(memory_total, int)
        or memory_total <= 0
    ):
        raise GPUDeviceBindingError(
            "NVIDIA-SMI must report a valid total VRAM capacity"
        )
    if (
        isinstance(memory_free, bool)
        or not isinstance(memory_free, int)
        or memory_free < 0
    ):
        raise GPUDeviceBindingError(
            "NVIDIA-SMI must report a valid free VRAM reading"
        )
    if memory_free > memory_total:
        raise GPUDeviceBindingError(
            "NVIDIA-SMI free VRAM exceeds the reported total capacity"
        )
    if memory_free < MIN_FREE_VRAM_MIB:
        raise GPUDeviceBindingError(
            f"insufficient free VRAM: {memory_free} MiB available; "
            f"at least {MIN_FREE_VRAM_MIB} MiB required"
        )

    vulkan_binding = resolve_vulkan_dxgi_adapter(
        gpu_report, target_name=target_name
    )
    if gpu_report.get("vram_budget_6gb_detected") is not True:
        raise GPUDeviceBindingError(
            "Vulkan loader, device inventory, DXGI LUID match, and 6GB VRAM checks must all pass"
        )

    if anime4k_report.get("status") != "ok":
        raise GPUDeviceBindingError("Anime4KCPP processor/device inventory is unavailable")
    if not (
        (anime4k_report.get("processor_probe") or {}).get("success") is True
        and (anime4k_report.get("device_probe") or {}).get("success") is True
    ):
        raise GPUDeviceBindingError("Anime4KCPP --lp/-l probes did not both succeed")

    recommendation = anime4k_report.get("recommended_gpu_processor_device")
    if not isinstance(recommendation, dict):
        raise GPUDeviceBindingError(
            "Anime4KCPP has no unique CUDA/OpenCL " + target_name + " device"
        )
    backend = recommendation.get("processor")
    index = recommendation.get("device_index")
    device_name = recommendation.get("device_name")
    if backend not in ("cuda", "opencl") or not _valid_device_index(index):
        raise GPUDeviceBindingError("Anime4KCPP recommended device selection is invalid")
    if backend not in (anime4k_report.get("available_processors") or []):
        raise GPUDeviceBindingError("Anime4KCPP recommended processor is not available")
    inventory = (anime4k_report.get("device_inventory_by_processor") or {}).get(backend) or []
    matches = [
        item for item in inventory
        if isinstance(item, dict) and _matches_target(item.get("name"), target_name)
    ]
    if (
        len(matches) != 1
        or not _valid_device_index(matches[0].get("index"))
        or matches[0].get("index") != index
        or matches[0].get("name") != device_name
    ):
        raise GPUDeviceBindingError(
            "Anime4KCPP target device index is missing or ambiguous"
        )

    return {
        "target_gpu": target_name,
        "ncnn_vulkan": {
            "backend": "vulkan",
            "device_index": vulkan_binding["device_index"],
            "device_name": vulkan_binding["device_name"],
            "device_luid": vulkan_binding["device_luid"],
            "dxgi_adapter_luid": vulkan_binding["dxgi_adapter_luid"],
            "device_node_mask": vulkan_binding["device_node_mask"],
            "luid_match_verified": True,
        },
        "vulkan_dxgi_luid_binding": vulkan_binding,
        "anime4k": {
            "backend": backend,
            "device_index": index,
            "device_name": device_name,
        },
        "binding_configured": True,
        "vram_preflight": {
            "total_mib": memory_total,
            "free_mib": memory_free,
            "minimum_free_mib": MIN_FREE_VRAM_MIB,
            "passed": True,
            "note": "Launch-time snapshot only; not a reservation or peak-memory guarantee.",
        },
        "runtime_device_use_verified": False,
        "note": (
            "The Vulkan physical-device LUID was matched to one DXGI adapter before "
            "launch; native process adapter use still requires runtime telemetry."
        ),
    }


def _set_option(args: list[str], flags: tuple[str, ...], value: str) -> list[str]:
    result = list(args)
    positions = [index for index, token in enumerate(result) if token in flags]
    if len(positions) > 1:
        raise GPUDeviceBindingError("duplicate CLI option: " + "/".join(flags))
    if positions:
        index = positions[0]
        if index + 1 >= len(result) or result[index + 1] in flags:
            raise GPUDeviceBindingError("CLI option has no value: " + result[index])
        result[index + 1] = str(value)
    else:
        result.extend((flags[0], str(value)))
    return result


def bind_manifest_data(manifest: dict, selection: dict) -> dict:
    """Return a copy of the four-engine manifest with explicit per-engine GPU flags."""
    if not isinstance(manifest, dict) or set(manifest) != set(ENGINES):
        raise GPUDeviceBindingError("manifest must contain exactly four engines")
    if selection.get("binding_configured") is not True:
        raise GPUDeviceBindingError("GPU selection has not passed the binding gate")

    vulkan = selection["ncnn_vulkan"]
    anime = selection["anime4k"]
    if not _valid_device_index(vulkan.get("device_index")):
        raise GPUDeviceBindingError("invalid NCNN Vulkan device index")
    if (
        vulkan.get("luid_match_verified") is not True
        or not _valid_luid_text(vulkan.get("device_luid"))
        or not _valid_luid_text(vulkan.get("dxgi_adapter_luid"))
        or vulkan["device_luid"].casefold() != vulkan["dxgi_adapter_luid"].casefold()
    ):
        raise GPUDeviceBindingError("NCNN Vulkan-to-DXGI LUID binding is not verified")
    if anime.get("backend") not in ("cuda", "opencl"):
        raise GPUDeviceBindingError("invalid Anime4KCPP processor")
    if not _valid_device_index(anime.get("device_index")):
        raise GPUDeviceBindingError("invalid Anime4KCPP device index")

    result = json.loads(json.dumps(manifest))
    for name in ENGINES:
        entry = result.get(name)
        if not isinstance(entry, dict):
            raise GPUDeviceBindingError(name + ": invalid manifest entry")
        args = entry.get("args")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise GPUDeviceBindingError(name + ": invalid CLI argument list")
        if name in NCNN_ENGINES:
            entry["args"] = _set_option(args, ("-g", "--gpu"), str(vulkan["device_index"]))
            entry["device_selection"] = {
                "backend": "vulkan",
                "device_index": vulkan["device_index"],
                "device_name": vulkan["device_name"],
                "device_luid": vulkan["device_luid"].casefold(),
                "dxgi_adapter_luid": vulkan["dxgi_adapter_luid"].casefold(),
                "luid_match_verified": True,
                "runtime_device_use_verified": False,
            }
        else:
            args = _set_option(args, ("-p", "--processor"), str(anime["backend"]))
            entry["args"] = _set_option(args, ("-d", "--device"), str(anime["device_index"]))
            entry["device_selection"] = {
                "backend": anime["backend"],
                "device_index": anime["device_index"],
                "device_name": anime["device_name"],
                "runtime_device_use_verified": False,
            }
    return result


def write_bound_manifest(
    source_path: Path,
    destination_path: Path,
    gpu_report: dict,
    anime4k_report: dict,
    *,
    target_name: str = TARGET_GPU,
) -> dict:
    """Write an ephemeral, per-run manifest; never mutate the installed manifest."""
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    try:
        original = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise GPUDeviceBindingError("installed manifest cannot be read") from exc
    selection = resolve_device_selection(
        gpu_report, anime4k_report, target_name=target_name
    )
    bound = bind_manifest_data(original, selection)
    if destination_path.exists():
        raise GPUDeviceBindingError("runtime-bound manifest destination already exists")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        json.dumps(bound, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return selection
