from tools.v211_gpu_process_telemetry import evaluate_pid_observations


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
