from tools.v211_gpu_process_telemetry import (
    evaluate_pid_observations, validate_runtime_vram_snapshot,
)


def _device(index, name, *, graphics=None, compute=None):
    return {
        "index": index,
        "name": name,
        "apis": {
            "graphics": {"available": True, "processes": graphics or []},
            "compute": {"available": True, "processes": compute or []},
        },
    }


def test_verifies_live_pid_on_unique_target_adapter_with_nonzero_memory():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                graphics=[{"pid": 4321, "used_gpu_memory_bytes": 64 * 1024 * 1024}],
            ),
            _device(1, "NVIDIA RTX 4060"),
        ],
        process_api_available=True,
    )

    assert result["verified"] is True
    assert result["status"] == "verified"
    assert result["adapter_index"] == 0
    assert result["adapter_name"] == "NVIDIA GeForce GTX 1660 Ti"
    assert result["backend_apis"] == ["graphics"]


def test_compute_process_is_also_detected():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                compute=[{"pid": 4321, "used_gpu_memory_bytes": 32 * 1024 * 1024}],
            )
        ],
        process_api_available=True,
    )

    assert result["verified"] is True
    assert result["backend_apis"] == ["compute"]


def test_fails_closed_when_pid_is_not_visible_on_any_adapter():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [_device(0, "NVIDIA GeForce GTX 1660 Ti")],
        process_api_available=True,
    )

    assert result["verified"] is False
    assert result["status"] == "pid_not_observed"


def test_fails_closed_when_process_memory_is_unavailable_or_zero():
    for memory in (None, 0, (1 << 64) - 1):
        result = evaluate_pid_observations(
            4321,
            "gtx 1660 ti",
            [
                _device(
                    0,
                    "NVIDIA GeForce GTX 1660 Ti",
                    graphics=[{"pid": 4321, "used_gpu_memory_bytes": memory}],
                )
            ],
            process_api_available=True,
        )
        assert result["verified"] is False
        assert result["status"] == "gpu_memory_not_confirmed"


def test_fails_closed_when_pid_is_seen_on_a_different_adapter():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(0, "NVIDIA GeForce GTX 1660 Ti"),
            _device(
                1,
                "NVIDIA RTX 4060",
                compute=[{"pid": 4321, "used_gpu_memory_bytes": 64 * 1024 * 1024}],
            ),
        ],
        process_api_available=True,
    )

    assert result["verified"] is False
    assert result["status"] == "pid_seen_on_wrong_adapter"


def test_fails_closed_when_pid_appears_on_multiple_adapters():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                graphics=[{"pid": 4321, "used_gpu_memory_bytes": 64 * 1024 * 1024}],
            ),
            _device(
                1,
                "NVIDIA RTX 4060",
                compute=[{"pid": 4321, "used_gpu_memory_bytes": 64 * 1024 * 1024}],
            ),
        ],
        process_api_available=True,
    )

    assert result["verified"] is False
    assert result["status"] == "pid_seen_on_multiple_adapters"


def test_fails_closed_for_ambiguous_same_model_target_adapters():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(0, "NVIDIA GeForce GTX 1660 Ti"),
            _device(1, "NVIDIA GeForce GTX 1660 Ti"),
        ],
        process_api_available=True,
    )

    assert result["verified"] is False
    assert result["status"] == "target_adapter_ambiguous"


def test_fails_closed_when_nvml_process_accounting_is_unavailable():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [_device(0, "NVIDIA GeForce GTX 1660 Ti")],
        process_api_available=False,
    )

    assert result["verified"] is False
    assert result["status"] == "process_api_unavailable"



def test_frozen_candidate_and_windows_ci_include_runtime_telemetry():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = (root / "NiyomsilV2ArmCore.spec").read_text(encoding="utf-8")
    workflow = (
        root / ".github" / "workflows" / "v211-four-engine-bridge-windows.yml"
    ).read_text(encoding="utf-8")

    assert '"tools.v211_gpu_process_telemetry"' in spec
    assert "tests/test_v211_gpu_process_telemetry.py" in workflow


def test_wddm_pid_with_unavailable_nvml_memory_requires_live_gpu_engine_activity():
    from tools.v211_gpu_process_telemetry import evaluate_pid_observations

    activity = {
        "available": True,
        "verified": True,
        "status": "gpu_engine_activity_observed",
        "source": "windows_gpu_engine_pdh",
        "pid": 4321,
        "sample_count": 2,
        "counter_count": 3,
        "active_sample_count": 1,
        "max_utilization_percent": 4.25,
        "adapter_luid": "0x00000000_0x0000e7f7",
        "target_adapter_luid": "0x00000000_0x0000e7f7",
    }
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                graphics=[{"pid": 4321, "used_gpu_memory_bytes": None}],
            )
        ],
        process_api_available=True,
        gpu_activity=activity,
    )

    assert result["verified"] is True
    assert result["status"] == "verified"
    assert result["evidence_source"] == "nvml_pid_plus_windows_gpu_engine_pdh"
    assert result["adapter_index"] == 0
    assert result["gpu_engine_sample_count"] == 2
    assert result["gpu_engine_active_sample_count"] == 1
    assert result["gpu_engine_max_utilization_percent"] == 4.25
    assert result["gpu_engine_adapter_luid_match"] is True
    assert result["gpu_engine_adapter_luid"] == "0x00000000_0x0000e7f7"


def test_wddm_pid_without_active_gpu_engine_sample_fails_closed():
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                graphics=[{"pid": 4321, "used_gpu_memory_bytes": None}],
            )
        ],
        process_api_available=True,
        gpu_activity={
            "available": True,
            "verified": False,
            "status": "gpu_engine_activity_not_observed",
            "source": "windows_gpu_engine_pdh",
            "pid": 4321,
            "sample_count": 2,
            "counter_count": 2,
            "active_sample_count": 0,
            "max_utilization_percent": 0.0,
            "adapter_luid": "0x00000000_0x0000e7f7",
            "target_adapter_luid": "0x00000000_0x0000e7f7",
        },
    )

    assert result["verified"] is False
    assert result["status"] == "gpu_memory_not_confirmed"


def test_wddm_gpu_engine_activity_must_match_pid_and_have_positive_utilization():
    base = {
        "available": True,
        "verified": True,
        "status": "gpu_engine_activity_observed",
        "source": "windows_gpu_engine_pdh",
        "pid": 9999,
        "sample_count": 2,
        "counter_count": 1,
        "active_sample_count": 1,
        "max_utilization_percent": 1.0,
        "adapter_luid": "0x00000000_0x0000e7f7",
        "target_adapter_luid": "0x00000000_0x0000e7f7",
    }
    devices = [
        _device(
            0,
            "NVIDIA GeForce GTX 1660 Ti",
            compute=[{"pid": 4321, "used_gpu_memory_bytes": None}],
        )
    ]
    wrong_pid = evaluate_pid_observations(
        4321, "gtx 1660 ti", devices,
        process_api_available=True, gpu_activity=base,
    )
    assert wrong_pid["verified"] is False

    zero_activity = dict(base, pid=4321, max_utilization_percent=0.0)
    no_work = evaluate_pid_observations(
        4321, "gtx 1660 ti", devices,
        process_api_available=True, gpu_activity=zero_activity,
    )
    assert no_work["verified"] is False

    one_sample = dict(
        base, pid=4321, sample_count=1,
        adapter_luid="0x00000000_0x0000e7f7",
        target_adapter_luid="0x00000000_0x0000e7f7",
    )
    insufficient_samples = evaluate_pid_observations(
        4321, "gtx 1660 ti", devices,
        process_api_available=True, gpu_activity=one_sample,
    )
    assert insufficient_samples["verified"] is False

    wrong_adapter = dict(
        base, pid=4321,
        adapter_luid="0x00000000_0x0000e7f7",
        target_adapter_luid="0x00000000_0x0000f1a1",
    )
    adapter_mismatch = evaluate_pid_observations(
        4321, "gtx 1660 ti", devices,
        process_api_available=True, gpu_activity=wrong_adapter,
    )
    assert adapter_mismatch["verified"] is False


def test_windows_gpu_engine_instance_parser_matches_exact_pid_tokens():
    from tools.v211_gpu_process_telemetry import NvmlProcessProbe

    assert NvmlProcessProbe._instance_matches_pid(
        "pid_4321_luid_0x00000000_0x0000A1B2_phys_0_engtype_3D_0", 4321
    )
    assert NvmlProcessProbe._instance_matches_pid("pid_4321_engtype_Compute_0", 4321)
    assert not NvmlProcessProbe._instance_matches_pid("pid_14321_engtype_3D_0", 4321)
    assert not NvmlProcessProbe._instance_matches_pid("pid_43210_engtype_3D_0", 4321)


def test_nvml_process_info_v1_v2_v3_use_version_correct_struct_sizes():
    import ctypes
    from tools.v211_gpu_process_telemetry import (
        _ProcessInfoV1,
        _ProcessInfoV2,
        _ProcessInfoV3,
    )

    assert ctypes.sizeof(_ProcessInfoV1) == 16
    assert ctypes.sizeof(_ProcessInfoV2) == 24
    assert ctypes.sizeof(_ProcessInfoV3) == 24


def test_gpu_engine_luid_parser_uses_high_low_order_and_rejects_missing_luid():
    from tools.v211_gpu_process_telemetry import NvmlProcessProbe

    instance = "pid_4321_luid_0x00000000_0x0000e7f7_phys_0_eng_0_engtype_3d"
    assert NvmlProcessProbe._parse_gpu_engine_luid(instance) == (0, 0xE7F7)
    assert NvmlProcessProbe._parse_gpu_engine_luid(
        "pid_4321_engtype_3d_0"
    ) is None


def test_wddm_target_luid_requires_one_matching_nvidia_dxgi_adapter(monkeypatch):
    from tools import v211_gpu_process_telemetry as telemetry

    probe = telemetry.NvmlProcessProbe.__new__(telemetry.NvmlProcessProbe)
    probe.target_name = "gtx 1660 ti"
    probe._dxgi_adapters = None
    probe._dxgi_status = "not_initialized"
    adapters = [
        {
            "description": "NVIDIA GeForce GTX 1660 Ti",
            "vendor_id": 0x10DE,
            "luid": (0, 0xE7F7),
        },
        {
            "description": "Intel UHD Graphics",
            "vendor_id": 0x8086,
            "luid": (0, 0x1100A),
        },
    ]
    monkeypatch.setattr(telemetry, "_enumerate_dxgi_adapters", lambda: adapters)
    assert probe._target_dxgi_luid() == (0, 0xE7F7)

    probe._dxgi_adapters = None
    monkeypatch.setattr(
        telemetry, "_enumerate_dxgi_adapters",
        lambda: adapters + [dict(adapters[0], luid=(0, 0xF1A1))],
    )
    assert probe._target_dxgi_luid() is None
    assert probe._dxgi_status == "target_dxgi_adapter_not_unique"


def test_wddm_gpu_engine_activity_rejects_malformed_luid_even_when_strings_match():
    activity = {
        "available": True,
        "verified": True,
        "status": "gpu_engine_activity_observed",
        "source": "windows_gpu_engine_pdh",
        "pid": 4321,
        "sample_count": 2,
        "counter_count": 1,
        "active_sample_count": 1,
        "max_utilization_percent": 1.0,
        "adapter_luid": "gtx-1660-ti",
        "target_adapter_luid": "gtx-1660-ti",
    }
    result = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        [
            _device(
                0,
                "NVIDIA GeForce GTX 1660 Ti",
                graphics=[{"pid": 4321, "used_gpu_memory_bytes": None}],
            )
        ],
        process_api_available=True,
        gpu_activity=activity,
    )
    assert result["verified"] is False


def test_pdh_object_cache_refresh_uses_enum_objects_brefresh_contract():
    import ctypes
    from tools.v211_gpu_process_telemetry import (
        NvmlProcessProbe,
        PDH_MORE_DATA,
        PDH_SUCCESS,
        PERF_DETAIL_WIZARD,
    )

    calls = []

    def fake_enum_objects(_source, _machine, buffer, size_pointer, detail, refresh):
        calls.append((buffer is None, detail, refresh))
        if buffer is None:
            size_pointer._obj.value = 2
            return PDH_MORE_DATA
        return PDH_SUCCESS

    probe = NvmlProcessProbe.__new__(NvmlProcessProbe)
    probe._pdh_functions = {"PdhEnumObjectsW": fake_enum_objects}

    assert probe._refresh_pdh_object_cache() is True
    assert calls == [
        (True, PERF_DETAIL_WIZARD, 1),
        (False, PERF_DETAIL_WIZARD, 0),
    ]


def test_wddm_active_sample_count_counts_samples_not_active_counters():
    import ctypes
    from tools.v211_gpu_process_telemetry import (
        NvmlProcessProbe,
        PDH_CSTATUS_VALID_DATA,
        PDH_FMT_DOUBLE,
        PDH_SUCCESS,
    )

    probe = NvmlProcessProbe.__new__(NvmlProcessProbe)
    session = {
        "query": ctypes.c_void_p(100),
        "counters": [
            (ctypes.c_void_p(1), "gpu-engine-a"),
            (ctypes.c_void_p(2), "gpu-engine-b"),
        ],
        "sample_count": 1,
        "active_sample_count": 0,
        "counter_count": 2,
        "target_adapter_luid": "0x00000000_0x0000e7f7",
    }
    probe._pdh_sessions = {4321: session}

    def collect(_query):
        return PDH_SUCCESS

    def get_value(counter, value_format, _type_pointer, output):
        assert value_format == PDH_FMT_DOUBLE
        output._obj.CStatus = PDH_CSTATUS_VALID_DATA
        output._obj.value.doubleValue = 5.0 if counter.value == 1 else 12.5
        return PDH_SUCCESS

    probe._pdh_functions = {
        "PdhCollectQueryData": collect,
        "PdhGetFormattedCounterValue": get_value,
    }

    result = probe._sample_windows_gpu_engine_activity(4321)

    assert result["verified"] is True
    assert result["sample_count"] == 2
    assert result["counter_count"] == 2
    # Two active engine counters in one PDH collection are still one active sample.
    assert result["active_sample_count"] == 1
    assert result["max_utilization_percent"] == 12.5


def test_wddm_activity_rejects_inconsistent_sample_counts_and_out_of_range_utilization():
    from tools.v211_gpu_process_telemetry import evaluate_pid_observations

    devices = [
        _device(
            0,
            "NVIDIA GeForce GTX 1660 Ti",
            graphics=[{"pid": 4321, "used_gpu_memory_bytes": None}],
        )
    ]
    base = {
        "available": True,
        "verified": True,
        "source": "windows_gpu_engine_pdh",
        "pid": 4321,
        "sample_count": 2,
        "counter_count": 2,
        "active_sample_count": 1,
        "max_utilization_percent": 12.5,
        "adapter_luid": "0x00000000_0x0000e7f7",
        "target_adapter_luid": "0x00000000_0x0000e7f7",
    }

    too_many_active_samples = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        devices,
        process_api_available=True,
        gpu_activity=dict(base, active_sample_count=3),
    )
    assert too_many_active_samples["verified"] is False

    impossible_utilization = evaluate_pid_observations(
        4321,
        "gtx 1660 ti",
        devices,
        process_api_available=True,
        gpu_activity=dict(base, max_utilization_percent=125.0),
    )
    assert impossible_utilization["verified"] is False


def test_pdh_counter_path_uses_local_machine_single_separator_syntax(monkeypatch):
    import ctypes
    from tools.v211_gpu_process_telemetry import (
        NvmlProcessProbe,
        PDH_SUCCESS,
    )

    instance = (
        "pid_4321_luid_0x00000000_0x0000e7f7_phys_0_eng_0_engtype_3D_0"
    )
    paths = []
    probe = NvmlProcessProbe.__new__(NvmlProcessProbe)
    probe._pdh_status = "ready"
    probe._pdh_functions = {}

    def open_query(_source, _user_data, output):
        output._obj.value = 100
        return PDH_SUCCESS

    def add_counter(_query, path, _user_data, output):
        paths.append(path)
        output._obj.value = 200 + len(paths)
        return PDH_SUCCESS

    probe._pdh_functions.update({
        "PdhOpenQueryW": open_query,
        "PdhAddCounterW": add_counter,
        "PdhCollectQueryData": lambda _query: PDH_SUCCESS,
        "PdhCloseQuery": lambda _query: PDH_SUCCESS,
    })
    monkeypatch.setattr(probe, "_load_pdh", lambda: object())
    monkeypatch.setattr(probe, "_target_dxgi_luid", lambda: (0, 0xE7F7))
    monkeypatch.setattr(probe, "_refresh_pdh_object_cache", lambda: True)
    monkeypatch.setattr(probe, "_localized_pdh_name", lambda name: name)
    monkeypatch.setattr(
        probe,
        "_enumerate_pdh_instances",
        lambda object_name: [instance] if object_name == "GPU Engine" else [],
    )

    session = probe._create_pdh_session(4321)

    assert session is not None
    assert paths == [
        "\\GPU Engine(pid_4321_luid_0x00000000_0x0000e7f7_phys_0_eng_0_engtype_3D_0)\\Utilization Percentage"
    ]
    assert not paths[0].startswith("\\\\")
    assert ")\\\\" not in paths[0]


def test_runtime_vram_snapshot_records_peak_inputs_and_preserves_512_mib_reserve():
    mib = 1024 * 1024
    safe = validate_runtime_vram_snapshot({
        "device_memory_available": True,
        "device_memory_status": "ok",
        "device_memory_total_bytes": 6144 * mib,
        "device_memory_used_bytes": 5632 * mib,
        "device_memory_free_bytes": 512 * mib,
    })
    assert safe["passed"] is True
    assert safe["status"] == "ok"
    assert safe["total_mib"] == 6144.0
    assert safe["used_mib"] == 5632.0
    assert safe["free_mib"] == 512.0


def test_runtime_vram_snapshot_blocks_below_reserve_and_missing_telemetry():
    mib = 1024 * 1024
    low = validate_runtime_vram_snapshot({
        "device_memory_available": True,
        "device_memory_status": "ok",
        "device_memory_total_bytes": 6144 * mib,
        "device_memory_used_bytes": 5633 * mib,
        "device_memory_free_bytes": 511 * mib,
    })
    assert low["passed"] is False
    assert low["status"] == "reserve_breached"
    missing = validate_runtime_vram_snapshot({"verified": True})
    assert missing["passed"] is False
    assert missing["status"] == "telemetry_unavailable"


def test_runtime_vram_snapshot_rejects_boolean_and_impossible_memory_values():
    mib = 1024 * 1024
    boolean = validate_runtime_vram_snapshot({
        "device_memory_available": True,
        "device_memory_status": "ok",
        "device_memory_total_bytes": True,
        "device_memory_used_bytes": 0,
        "device_memory_free_bytes": 6144 * mib,
    })
    impossible = validate_runtime_vram_snapshot({
        "device_memory_available": True,
        "device_memory_status": "ok",
        "device_memory_total_bytes": 6144 * mib,
        "device_memory_used_bytes": 7000 * mib,
        "device_memory_free_bytes": 1 * mib,
    })
    assert boolean["status"] == "invalid_snapshot"
    assert impossible["status"] == "invalid_snapshot"


def test_nvml_device_memory_query_returns_only_numeric_snapshot_fields():
    import ctypes
    from tools import v211_gpu_process_telemetry as telemetry

    probe = telemetry.NvmlProcessProbe.__new__(telemetry.NvmlProcessProbe)
    def fake_memory_query(_handle, pointer):
        memory = ctypes.cast(
            pointer, ctypes.POINTER(telemetry._NvmlMemoryInfo)
        ).contents
        memory.total = 6144 * 1024 * 1024
        memory.free = 4096 * 1024 * 1024
        memory.used = 2048 * 1024 * 1024
        return telemetry.NVML_SUCCESS
    probe._memory_function = fake_memory_query
    result = probe._query_device_memory({"handle": ctypes.c_void_p(1)})
    assert result["device_memory_available"] is True
    assert result["device_memory_status"] == "ok"
    assert result["device_memory_total_bytes"] == 6144 * 1024 * 1024
    assert result["device_memory_free_bytes"] == 4096 * 1024 * 1024
    assert result["device_memory_used_bytes"] == 2048 * 1024 * 1024
