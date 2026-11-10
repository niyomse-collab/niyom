"""Fail-closed NVML/WDDM process-to-adapter telemetry for V2.1.1 engines.

A live native PID must be visible on the unique requested NVIDIA adapter and
must have either non-zero NVML process memory or matching active Windows GPU
Engine counters when WDDM reports NVML memory as unavailable. This does not
certify image quality, throughput, or that every instruction executed on GPU.
Unavailable/unsupported process accounting remains unverified.
"""
from __future__ import annotations

import ctypes
import math
import os
import re
from pathlib import Path
from typing import Any

NVML_SUCCESS = 0
NVML_ERROR_INSUFFICIENT_SIZE = 7
NVML_ERROR_NOT_SUPPORTED = 3
NVML_VALUE_NOT_AVAILABLE = (1 << 64) - 1

PDH_SUCCESS = 0
PDH_MORE_DATA = 0x800007D2
PDH_FMT_DOUBLE = 0x00000200
PDH_CSTATUS_VALID_DATA = 0
PDH_CSTATUS_NEW_DATA = 1
PERF_DETAIL_WIZARD = 400


class _PdhValueUnion(ctypes.Union):
    _fields_ = [
        ("doubleValue", ctypes.c_double),
        ("longValue", ctypes.c_long),
        ("largeValue", ctypes.c_longlong),
        ("ansiStringValue", ctypes.c_char_p),
        ("wideStringValue", ctypes.c_wchar_p),
    ]


class _PdhFormattedCounterValue(ctypes.Structure):
    _fields_ = [
        ("CStatus", ctypes.c_uint),
        ("value", _PdhValueUnion),
    ]


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class _DxgiAdapterDesc1(ctypes.Structure):
    _fields_ = [
        ("Description", ctypes.c_wchar * 128),
        ("VendorId", ctypes.c_uint32),
        ("DeviceId", ctypes.c_uint32),
        ("SubSysId", ctypes.c_uint32),
        ("Revision", ctypes.c_uint32),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _Luid),
        ("Flags", ctypes.c_uint32),
    ]


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _enumerate_dxgi_adapters() -> list[dict[str, Any]]:
    """Enumerate DXGI adapter descriptions and their OS-assigned LUIDs."""
    if os.name != "nt":
        return []
    try:
        loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
        dxgi = loader("dxgi.dll")
        create_factory = dxgi.CreateDXGIFactory1
        create_factory.argtypes = [
            ctypes.POINTER(_Guid), ctypes.POINTER(ctypes.c_void_p)
        ]
        create_factory.restype = ctypes.c_long
        iid = _Guid(
            0x770AAE78, 0xF26F, 0x4DBA,
            (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87),
        )
        factory = ctypes.c_void_p()
        if int(create_factory(ctypes.byref(iid), ctypes.byref(factory))) != 0 or not factory:
            return []
        prototype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        factory_vtable = ctypes.cast(
            factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        enum_adapters = prototype(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        )(factory_vtable[12])
        release = prototype(ctypes.c_uint32, ctypes.c_void_p)(
            factory_vtable[2]
        )
        results = []
        try:
            for index in range(32):
                adapter = ctypes.c_void_p()
                hr = int(enum_adapters(factory, index, ctypes.byref(adapter)))
                if (hr & 0xFFFFFFFF) == 0x887A0002:
                    break
                if hr < 0 or not adapter:
                    continue
                try:
                    adapter_vtable = ctypes.cast(
                        adapter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                    ).contents
                    get_desc1 = prototype(
                        ctypes.c_long, ctypes.c_void_p,
                        ctypes.POINTER(_DxgiAdapterDesc1),
                    )(adapter_vtable[10])
                    desc = _DxgiAdapterDesc1()
                    if int(get_desc1(adapter, ctypes.byref(desc))) != 0:
                        continue
                    high = int(desc.AdapterLuid.HighPart) & 0xFFFFFFFF
                    low = int(desc.AdapterLuid.LowPart) & 0xFFFFFFFF
                    results.append({
                        "description": str(desc.Description),
                        "vendor_id": int(desc.VendorId),
                        "device_id": int(desc.DeviceId),
                        "dedicated_video_memory_bytes": int(desc.DedicatedVideoMemory),
                        "luid": (high, low),
                        "luid_text": f"0x{high:08x}_0x{low:08x}",
                    })
                finally:
                    try:
                        release(adapter)
                    except Exception:
                        pass
        finally:
            try:
                release(factory)
            except Exception:
                pass
        return results
    except (AttributeError, OSError, TypeError, ValueError):
        return []


class _ProcessInfoV1(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_uint64),
    ]


class _ProcessInfoV2(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_uint64),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


class _ProcessInfoV3(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_uint64),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


def _valid_wddm_gpu_activity(pid: int, activity: object) -> bool:
    """Validate a two-sample Windows GPU Engine activity observation."""
    if not isinstance(activity, dict):
        return False
    samples = activity.get("sample_count")
    active_samples = activity.get("active_sample_count")
    counters = activity.get("counter_count")
    observed_pid = activity.get("pid")
    utilization = activity.get("max_utilization_percent")
    return bool(
        activity.get("available") is True
        and activity.get("verified") is True
        and activity.get("source") == "windows_gpu_engine_pdh"
        and observed_pid == pid
        and isinstance(activity.get("adapter_luid"), str)
        and bool(activity.get("adapter_luid"))
        and activity.get("adapter_luid") == activity.get("target_adapter_luid")
        and isinstance(samples, int) and not isinstance(samples, bool) and samples >= 2
        and isinstance(active_samples, int) and not isinstance(active_samples, bool) and active_samples >= 1
        and isinstance(counters, int) and not isinstance(counters, bool) and counters >= 1
        and isinstance(utilization, (int, float)) and not isinstance(utilization, bool)
        and math.isfinite(float(utilization)) and float(utilization) > 0.0
    )


def evaluate_pid_observations(
    pid: int,
    target_name: str,
    devices: list[dict[str, Any]],
    *,
    process_api_available: bool,
    gpu_activity: object = None,
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
        if _valid_wddm_gpu_activity(pid, gpu_activity):
            return {
                "available": True,
                "verified": True,
                "status": "verified",
                "evidence_source": "nvml_pid_plus_windows_gpu_engine_pdh",
                "adapter_name": match["name"],
                "adapter_index": match["index"],
                "backend_apis": sorted(match["apis"]),
                "gpu_engine_sample_count": int(gpu_activity["sample_count"]),
                "gpu_engine_active_sample_count": int(gpu_activity["active_sample_count"]),
                "gpu_engine_max_utilization_percent": float(
                    gpu_activity["max_utilization_percent"]
                ),
                "gpu_engine_counter_count": int(gpu_activity["counter_count"]),
            }
        return {
            "available": True,
            "verified": False,
            "status": "gpu_memory_not_confirmed",
            "evidence_source": "nvml_pid_memory_unavailable",
            "adapter_name": match["name"],
            "adapter_index": match["index"],
            "backend_apis": sorted(match["apis"]),
            "gpu_activity_status": (
                gpu_activity.get("status")
                if isinstance(gpu_activity, dict) else "not_sampled"
            ),
        }
    return {
        "available": True,
        "verified": True,
        "status": "verified",
        "evidence_source": "nvml_process_memory",
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
        self._pdh_library = None
        self._pdh_functions: dict[str, Any] = {}
        self._pdh_sessions: dict[int, dict[str, Any]] = {}
        self._pdh_name_cache: dict[str, str] = {}
        self._pdh_status = "not_initialized"
        self._dxgi_adapters: list[dict[str, Any]] | None = None
        self._dxgi_status = "not_initialized"
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
            program_files = os.environ.get("ProgramFiles")
            if program_files:
                candidates.append(
                    str(Path(program_files) / "NVIDIA Corporation" / "NVSMI" / "nvml.dll")
                )
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

        pointer_v3 = ctypes.POINTER(_ProcessInfoV3)
        pointer_v2 = ctypes.POINTER(_ProcessInfoV2)
        pointer_v1 = ctypes.POINTER(_ProcessInfoV1)
        for family in ("Graphics", "Compute"):
            candidates = []
            for version, info_type, info_pointer in (
                (3, _ProcessInfoV3, pointer_v3),
                (2, _ProcessInfoV2, pointer_v2),
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
        if (
            os.name == "nt"
            and result.get("status") == "gpu_memory_not_confirmed"
            and result.get("evidence_source") == "nvml_pid_memory_unavailable"
        ):
            activity = self._sample_windows_gpu_engine_activity(pid)
            if activity.get("verified") is True:
                result = evaluate_pid_observations(
                    pid, self.target_name, inventory,
                    process_api_available=any_api_available,
                    gpu_activity=activity,
                )
            else:
                result["gpu_activity_status"] = str(activity.get("status") or "unavailable")[:64]
        if engine:
            result["engine"] = str(engine)[:32]
        return result

    def _load_pdh(self):
        if self._pdh_library is not None:
            return self._pdh_library
        if self._pdh_status not in ("not_initialized", "ready"):
            return None
        if os.name != "nt":
            self._pdh_status = "windows_only"
            return None
        try:
            loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
            library = loader("pdh.dll")
            signatures = {
                "PdhOpenQueryW": (
                    [ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)],
                    ctypes.c_uint,
                ),
                "PdhCloseQuery": ([ctypes.c_void_p], ctypes.c_uint),
                "PdhAddCounterW": (
                    [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t,
                     ctypes.POINTER(ctypes.c_void_p)],
                    ctypes.c_uint,
                ),
                "PdhCollectQueryData": ([ctypes.c_void_p], ctypes.c_uint),
                "PdhGetFormattedCounterValue": (
                    [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint),
                     ctypes.POINTER(_PdhFormattedCounterValue)],
                    ctypes.c_uint,
                ),
                "PdhEnumObjectItemsW": (
                    [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                     ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(ctypes.c_uint),
                     ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(ctypes.c_uint),
                     ctypes.c_uint, ctypes.c_uint],
                    ctypes.c_uint,
                ),
                "PdhLookupPerfNameByIndexW": (
                    [ctypes.c_wchar_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_wchar),
                     ctypes.POINTER(ctypes.c_uint)],
                    ctypes.c_uint,
                ),
            }
            for name, (argtypes, restype) in signatures.items():
                function = getattr(library, name)
                function.argtypes = argtypes
                function.restype = restype
                self._pdh_functions[name] = function
            self._pdh_library = library
            self._pdh_status = "ready"
            return library
        except (AttributeError, OSError, TypeError):
            self._pdh_status = "pdh_library_or_api_unavailable"
            self._pdh_functions.clear()
            return None

    def _localized_pdh_name(self, english_name: str) -> str:
        cached = self._pdh_name_cache.get(english_name)
        if cached:
            return cached
        fallback = english_name
        try:
            import winreg
            key_path = (
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Perflib\009"
            )
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
            ) as key:
                pairs, _kind = winreg.QueryValueEx(key, "Counter")
            index = None
            for offset in range(0, len(pairs) - 1, 2):
                if str(pairs[offset + 1]).casefold() == english_name.casefold():
                    index = int(pairs[offset])
                    break
            if index is not None:
                lookup = self._pdh_functions["PdhLookupPerfNameByIndexW"]
                size = ctypes.c_uint(0)
                status = int(lookup(None, index, None, ctypes.byref(size)))
                if status in (PDH_MORE_DATA, PDH_SUCCESS) and size.value > 0:
                    buffer = ctypes.create_unicode_buffer(size.value)
                    status = int(lookup(None, index, buffer, ctypes.byref(size)))
                    if status == PDH_SUCCESS and buffer.value:
                        fallback = buffer.value
        except (ImportError, OSError, ValueError, TypeError, KeyError):
            pass
        self._pdh_name_cache[english_name] = fallback
        return fallback

    def _enumerate_pdh_instances(self, object_name: str) -> list[str]:
        enum_items = self._pdh_functions["PdhEnumObjectItemsW"]
        counter_size = ctypes.c_uint(0)
        instance_size = ctypes.c_uint(0)
        status = int(enum_items(
            None, None, object_name, None, ctypes.byref(counter_size),
            None, ctypes.byref(instance_size), PERF_DETAIL_WIZARD, 0,
        ))
        if status not in (PDH_MORE_DATA, PDH_SUCCESS) or instance_size.value < 2:
            return []
        for _attempt in range(2):
            counter_buffer = ctypes.create_unicode_buffer(max(1, counter_size.value))
            instance_buffer = ctypes.create_unicode_buffer(max(1, instance_size.value))
            status = int(enum_items(
                None, None, object_name, counter_buffer, ctypes.byref(counter_size),
                instance_buffer, ctypes.byref(instance_size), PERF_DETAIL_WIZARD, 0,
            ))
            if status == PDH_SUCCESS:
                raw = ctypes.wstring_at(
                    ctypes.addressof(instance_buffer), max(1, instance_size.value)
                )
                return [item for item in raw.split("\0") if item]
            if status != PDH_MORE_DATA:
                return []
        return []

    @staticmethod
    def _instance_matches_pid(instance: str, pid: int) -> bool:
        match = re.search(r"(?:^|_)pid_(\d+)(?:_|$)", str(instance), re.IGNORECASE)
        return bool(match and int(match.group(1)) == pid)

    @staticmethod
    def _parse_gpu_engine_luid(instance: str) -> tuple[int, int] | None:
        match = re.search(
            r"(?:^|_)luid_0x([0-9a-f]{8})_0x([0-9a-f]{8})(?:_|$)",
            str(instance), re.IGNORECASE,
        )
        if not match:
            return None
        return int(match.group(1), 16), int(match.group(2), 16)

    def _target_dxgi_luid(self) -> tuple[int, int] | None:
        if self._dxgi_adapters is None:
            self._dxgi_adapters = _enumerate_dxgi_adapters()
            self._dxgi_status = "ready" if self._dxgi_adapters else "dxgi_adapter_enumeration_unavailable"
        matches = [
            item for item in self._dxgi_adapters
            if item.get("vendor_id") == 0x10DE
            and self.target_name in str(item.get("description", "")).casefold()
        ]
        if len(matches) != 1:
            self._dxgi_status = "target_dxgi_adapter_not_unique"
            return None
        self._dxgi_status = "ready"
        return matches[0]["luid"]

    def _create_pdh_session(self, pid: int) -> dict[str, Any] | None:
        if self._load_pdh() is None:
            return None
        target_luid = self._target_dxgi_luid()
        if target_luid is None:
            return None
        target_luid_text = f"0x{target_luid[0]:08x}_0x{target_luid[1]:08x}"
        object_names = (
            self._localized_pdh_name("GPU Engine"),
            self._localized_pdh_name("GPU Process"),
        )
        counter_name = self._localized_pdh_name("Utilization Percentage")
        paths = []
        instances = []
        for object_name in dict.fromkeys(object_names):
            for instance in self._enumerate_pdh_instances(object_name):
                if (
                    self._instance_matches_pid(instance, pid)
                    and self._parse_gpu_engine_luid(instance) == target_luid
                ):
                    paths.append(f"\\{object_name}({instance})\\{counter_name}")
                    instances.append(instance)
        if not paths:
            return None
        query = ctypes.c_void_p()
        open_query = self._pdh_functions["PdhOpenQueryW"]
        if int(open_query(None, 0, ctypes.byref(query))) != PDH_SUCCESS:
            return None
        counters = []
        add_counter = self._pdh_functions["PdhAddCounterW"]
        for path, instance in zip(paths, instances):
            counter = ctypes.c_void_p()
            if int(add_counter(query, path, 0, ctypes.byref(counter))) == PDH_SUCCESS:
                counters.append((counter, instance))
        if not counters:
            self._pdh_functions["PdhCloseQuery"](query)
            return None
        collect = self._pdh_functions["PdhCollectQueryData"]
        if int(collect(query)) != PDH_SUCCESS:
            self._pdh_functions["PdhCloseQuery"](query)
            return None
        return {
            "query": query,
            "counters": counters,
            "sample_count": 1,
            "counter_count": len(counters),
            "target_adapter_luid": target_luid_text,
        }

    def _sample_windows_gpu_engine_activity(self, pid: int) -> dict[str, Any]:
        """Use WDDM GPU Engine counters when NVML exposes PID but not memory.

        NVIDIA documents usedGpuMemory as NVML_VALUE_NOT_AVAILABLE under WDDM.
        The fallback therefore requires both NVML's per-device PID attribution
        and live per-process GPU Engine utilization observed over two PDH samples.
        """
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return {"available": False, "verified": False, "status": "invalid_pid"}
        session = self._pdh_sessions.get(pid)
        if session is None:
            session = self._create_pdh_session(pid)
            if session is None:
                return {
                    "available": self._pdh_status == "ready",
                    "verified": False,
                    "status": (
                        self._dxgi_status
                        if self._dxgi_status != "ready"
                        else "pid_gpu_engine_counters_not_found"
                        if self._pdh_status == "ready" else self._pdh_status
                    ),
                }
            self._pdh_sessions[pid] = session
            return {
                "available": True,
                "verified": False,
                "status": "gpu_engine_sampling",
                "source": "windows_gpu_engine_pdh",
                "pid": pid,
                "sample_count": 1,
                "counter_count": session["counter_count"],
                "active_sample_count": 0,
                "max_utilization_percent": 0.0,
                "adapter_luid": session["target_adapter_luid"],
                "target_adapter_luid": session["target_adapter_luid"],
            }
        collect = self._pdh_functions["PdhCollectQueryData"]
        if int(collect(session["query"])) != PDH_SUCCESS:
            return {
                "available": True, "verified": False,
                "status": "gpu_engine_collect_failed",
            }
        session["sample_count"] += 1
        get_value = self._pdh_functions["PdhGetFormattedCounterValue"]
        maximum = 0.0
        active = 0
        for counter, _instance in session["counters"]:
            value = _PdhFormattedCounterValue()
            status = int(get_value(
                counter, PDH_FMT_DOUBLE, None, ctypes.byref(value)
            ))
            if status != PDH_SUCCESS:
                continue
            if value.CStatus not in (PDH_CSTATUS_VALID_DATA, PDH_CSTATUS_NEW_DATA):
                continue
            utilization = float(value.value.doubleValue)
            if math.isfinite(utilization) and utilization > 0.0:
                active += 1
                maximum = max(maximum, utilization)
        if active:
            return {
                "available": True,
                "verified": True,
                "status": "gpu_engine_activity_observed",
                "source": "windows_gpu_engine_pdh",
                "pid": pid,
                "sample_count": session["sample_count"],
                "counter_count": session["counter_count"],
                "active_sample_count": active,
                "max_utilization_percent": maximum,
                "adapter_luid": session["target_adapter_luid"],
                "target_adapter_luid": session["target_adapter_luid"],
            }
        return {
            "available": True,
            "verified": False,
            "status": "gpu_engine_activity_not_observed",
            "source": "windows_gpu_engine_pdh",
            "pid": pid,
            "sample_count": session["sample_count"],
            "counter_count": session["counter_count"],
            "active_sample_count": 0,
            "max_utilization_percent": 0.0,
            "adapter_luid": session["target_adapter_luid"],
            "target_adapter_luid": session["target_adapter_luid"],
        }

    def close_pid(self, pid: int | None) -> None:
        if isinstance(pid, bool) or not isinstance(pid, int):
            return
        session = self._pdh_sessions.pop(pid, None)
        if session is not None:
            try:
                self._pdh_functions["PdhCloseQuery"](session["query"])
            except (KeyError, OSError, TypeError):
                pass

    def close(self) -> None:
        for pid in tuple(self._pdh_sessions):
            self.close_pid(pid)
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
