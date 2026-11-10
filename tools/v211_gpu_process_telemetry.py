"""Fail-closed NVML process-to-adapter telemetry for V2.1.1 native engines.

This records only whether a live native process PID is visible on the unique
requested NVIDIA adapter with non-zero GPU memory allocated. It does not
certify image quality, throughput, or that every instruction executed on GPU.
Unavailable/unsupported NVML process accounting remains unverified.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any

NVML_SUCCESS = 0
NVML_ERROR_INSUFFICIENT_SIZE = 7
NVML_ERROR_NOT_SUPPORTED = 3
NVML_VALUE_NOT_AVAILABLE = (1 << 64) - 1


class _ProcessInfoV1(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_uint64),
    ]


class _ProcessInfoV3(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_uint64),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


def evaluate_pid_observations(
    pid: int,
    target_name: str,
    devices: list[dict[str, Any]],
    *,
    process_api_available: bool,
) -> dict[str, Any]:
    """Classify sampled NVML process lists without trusting caller booleans."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return {"available": bool(process_api_available), "verified": False, "status": "invalid_pid"}
    if not process_api_available:
        return {"available": False, "verified": False, "status": "process_api_unavailable"}
    if not isinstance(devices, list):
        return {"available": True, "verified": False, "status": "invalid_inventory"}

    target = str(target_name or "").casefold()
    target_devices = [
        item for item in devices
        if isinstance(item, dict)
        and target
        and target in str(item.get("name") or "").casefold()
    ]
    if len(target_devices) != 1:
        return {
            "available": True,
            "verified": False,
            "status": "target_adapter_missing" if not target_devices else "target_adapter_ambiguous",
        }

    matches: dict[int, dict[str, Any]] = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        index = device.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            continue
        apis = device.get("apis")
        if not isinstance(apis, dict):
            continue
        for api_name, api_data in apis.items():
            if not isinstance(api_data, dict) or api_data.get("available") is not True:
                continue
            processes = api_data.get("processes")
            if not isinstance(processes, list):
                continue
            for process in processes:
                if not isinstance(process, dict) or process.get("pid") != pid:
                    continue
                entry = matches.setdefault(index, {
                    "index": index,
                    "name": str(device.get("name") or "")[:160],
                    "memory_values": [],
                    "apis": set(),
                })
                entry["apis"].add(str(api_name)[:24])
                memory = process.get("used_gpu_memory_bytes")
                if (
                    isinstance(memory, int)
                    and not isinstance(memory, bool)
                    and 0 < memory < NVML_VALUE_NOT_AVAILABLE
                ):
                    entry["memory_values"].append(memory)

    if not matches:
        return {"available": True, "verified": False, "status": "pid_not_observed"}
    if len(matches) != 1:
        return {"available": True, "verified": False, "status": "pid_seen_on_multiple_adapters"}

    match = next(iter(matches.values()))
    if target not in match["name"].casefold():
        return {
            "available": True,
            "verified": False,
            "status": "pid_seen_on_wrong_adapter",
            "adapter_name": match["name"],
            "adapter_index": match["index"],
        }
    if not match["memory_values"]:
        return {
            "available": True,
            "verified": False,
            "status": "gpu_memory_not_confirmed",
            "adapter_name": match["name"],
            "adapter_index": match["index"],
            "backend_apis": sorted(match["apis"]),
        }
    return {
        "available": True,
        "verified": True,
        "status": "verified",
        "adapter_name": match["name"],
        "adapter_index": match["index"],
        "backend_apis": sorted(match["apis"]),
        "used_gpu_memory_bytes": max(match["memory_values"]),
    }


class NvmlProcessProbe:
    """Sample NVML graphics/compute process lists for a live child PID."""

    def __init__(self, target_name: str = "gtx 1660 ti") -> None:
        self.target_name = str(target_name or "gtx 1660 ti")
        self._library = None
        self._initialized = False
        self._devices: list[dict[str, Any]] = []
        self._process_functions: dict[str, list[tuple[str, Any, type]]] = {}
        self.status = "not_initialized"
        self._initialize()

    @staticmethod
    def _load_library():
        if os.name == "nt":
            loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
            candidates = ["nvml.dll"]
            system_root = os.environ.get("SystemRoot")
            if system_root:
                candidates.append(str(Path(system_root) / "System32" / "nvml.dll"))
        else:
            loader = ctypes.CDLL
            candidates = ["libnvidia-ml.so.1"]
        for candidate in candidates:
            try:
                return loader(candidate)
            except OSError:
                continue
        return None

    @staticmethod
    def _function(library, names, argtypes, restype=ctypes.c_int):
        for name in names:
            try:
                function = getattr(library, name)
            except AttributeError:
                continue
            try:
                function.argtypes = argtypes
                function.restype = restype
            except (AttributeError, TypeError):
                pass
            return function
        return None

    def _initialize(self) -> None:
        library = self._load_library()
        if library is None:
            self.status = "nvml_library_not_found"
            return
        self._library = library
        init = self._function(library, ("nvmlInit_v2", "nvmlInit"), [])
        if init is None:
            self.status = "nvml_init_symbol_missing"
            return
        try:
            result = int(init())
        except Exception:
            self.status = "nvml_init_failed"
            return
        if result != NVML_SUCCESS:
            self.status = "nvml_init_failed"
            return
        self._initialized = True

        count = ctypes.c_uint(0)
        get_count = self._function(
            library, ("nvmlDeviceGetCount_v2", "nvmlDeviceGetCount"),
            [ctypes.POINTER(ctypes.c_uint)],
        )
        get_handle = self._function(
            library, ("nvmlDeviceGetHandleByIndex_v2", "nvmlDeviceGetHandleByIndex"),
            [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
        )
        get_name = self._function(
            library, ("nvmlDeviceGetName",),
            [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint],
        )
        if not get_count or not get_handle or not get_name:
            self.status = "nvml_device_api_missing"
            return
        if int(get_count(ctypes.byref(count))) != NVML_SUCCESS or count.value < 1:
            self.status = "nvml_device_inventory_failed"
            return

        for index in range(int(count.value)):
            handle = ctypes.c_void_p()
            if int(get_handle(index, ctypes.byref(handle))) != NVML_SUCCESS:
                continue
            name_buffer = ctypes.create_string_buffer(96)
            if int(get_name(handle, name_buffer, len(name_buffer))) != NVML_SUCCESS:
                continue
            name = name_buffer.value.decode("utf-8", "replace").strip()
            if not name:
                continue
            self._devices.append({"index": index, "name": name, "handle": handle})

        if not self._devices:
            self.status = "nvml_device_inventory_empty"
            return

        pointer = ctypes.POINTER(_ProcessInfoV3)
        pointer_v1 = ctypes.POINTER(_ProcessInfoV1)
        for family in ("Graphics", "Compute"):
            candidates = []
            for version, info_type, info_pointer in (
                (3, _ProcessInfoV3, pointer),
                (2, _ProcessInfoV1, pointer_v1),
                (1, _ProcessInfoV1, pointer_v1),
            ):
                function = self._function(
                    library,
                    (f"nvmlDeviceGet{family}RunningProcesses_v{version}",),
                    [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), info_pointer],
                )
                if function is not None:
                    candidates.append((f"{family.lower()}_v{version}", function, info_type))
            self._process_functions[family.lower()] = candidates
        if not any(self._process_functions.values()):
            self.status = "nvml_process_api_missing"
            return
        self.status = "ready"

    @staticmethod
    def _query_process_list(function, info_type, handle):
        count = ctypes.c_uint(0)
        try:
            result = int(function(handle, ctypes.byref(count), None))
        except Exception:
            return False, []
        if result not in (NVML_SUCCESS, NVML_ERROR_INSUFFICIENT_SIZE):
            return False, []
        if count.value == 0:
            return True, []
        for _attempt in range(2):
            items = (info_type * int(count.value))()
            try:
                result = int(function(handle, ctypes.byref(count), items))
            except Exception:
                return False, []
            if result == NVML_SUCCESS:
                output = []
                for item in items[:int(count.value)]:
                    memory = int(item.usedGpuMemory)
                    output.append({
                        "pid": int(item.pid),
                        "used_gpu_memory_bytes": (
                            None if memory == NVML_VALUE_NOT_AVAILABLE else memory
                        ),
                    })
                return True, output
            if result != NVML_ERROR_INSUFFICIENT_SIZE or count.value < 1:
                return False, []
        return False, []

    def __call__(self, pid: int, engine: str | None = None) -> dict[str, Any]:
        if self.status != "ready":
            return {"available": False, "verified": False, "status": self.status}
        inventory = []
        any_api_available = False
        for device in self._devices:
            apis = {}
            for family, functions in self._process_functions.items():
                api_result = {"available": False, "processes": []}
                for api_name, function, info_type in functions:
                    available, processes = self._query_process_list(
                        function, info_type, device["handle"]
                    )
                    if available:
                        api_result = {
                            "available": True,
                            "processes": processes,
                            "api": api_name,
                        }
                        any_api_available = True
                        break
                apis[family] = api_result
            inventory.append({
                "index": device["index"],
                "name": device["name"],
                "apis": apis,
            })
        result = evaluate_pid_observations(
            pid, self.target_name, inventory,
            process_api_available=any_api_available,
        )
        if engine:
            result["engine"] = str(engine)[:32]
        return result

    def close(self) -> None:
        if not self._initialized or self._library is None:
            return
        shutdown = self._function(self._library, ("nvmlShutdown",), [])
        self._initialized = False
        if shutdown is not None:
            try:
                shutdown()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
