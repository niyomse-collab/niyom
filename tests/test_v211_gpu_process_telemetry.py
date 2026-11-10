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
