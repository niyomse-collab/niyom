from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from signprint_ai import v211_cuda_compat as compat


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("451.67", (451, 67, 0)),
        ("528.33", (528, 33, 0)),
        ("570.65", (570, 65, 0)),
        ("572.61.1", (572, 61, 1)),
        ("32.0.16.1742", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_nvidia_driver_version_uses_nvidia_smi_format(raw, expected):
    assert compat.parse_nvidia_driver_version(raw) == expected


@pytest.mark.parametrize(
    ("driver", "expected_status", "minor", "full"),
    [
        ("451.67", "below_cuda_12x_minor_compatibility_floor", False, False),
        ("528.33", "minor_compatibility_only_full_cuda_12_8_driver_not_met", True, False),
        ("560.94", "minor_compatibility_only_full_cuda_12_8_driver_not_met", True, False),
        ("570.65", "full_cuda_12_8_ga_driver_compatible", True, True),
    ],
)
def test_classify_cuda_driver_floor_is_diagnostic_only(driver, expected_status, minor, full):
    report = compat.classify_cuda_12_8_driver_compatibility([{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": driver,
    }])
    assert report["status"] == expected_status
    assert report["cuda_12x_minor_compatibility"] is minor
    assert report["cuda_12_8_ga_driver_requirement_met"] is full
    assert report["torch_cuda_runtime_initialized"] is False
    assert "Vulkan" in report["scope"]


def test_classify_fails_closed_for_missing_ambiguous_or_unparseable_target():
    missing = compat.classify_cuda_12_8_driver_compatibility([])
    ambiguous = compat.classify_cuda_12_8_driver_compatibility([
        {"name": "NVIDIA GeForce GTX 1660 Ti", "driver_version": "570.65"},
        {"name": "NVIDIA GeForce GTX 1660 Ti", "driver_version": "570.65"},
    ])
    unparseable = compat.classify_cuda_12_8_driver_compatibility([{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": "32.0.16.1742",
    }])
    assert missing["status"] == "target_gpu_missing_or_ambiguous"
    assert ambiguous["status"] == "target_gpu_missing_or_ambiguous"
    assert unparseable["status"] == "driver_version_unparseable"
    assert unparseable["cuda_12_8_ga_driver_requirement_met"] is None


def test_probe_is_read_only_and_uses_nvidia_smi_on_windows():
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout='"NVIDIA GeForce GTX 1660 Ti", 451.67\n',
            stderr="",
        )

    report = compat.probe_cuda_12_8_driver_compatibility(
        platform_name="nt",
        run=fake_run,
    )
    assert report["status"] == "below_cuda_12x_minor_compatibility_floor"
    assert report["driver_version"] == "451.67"
    assert calls[0][0] == [
        "nvidia-smi",
        "--query-gpu=name,driver_version",
        "--format=csv,noheader,nounits",
    ]
    assert calls[0][1]["timeout"] == 3
    assert calls[0][1]["check"] is False


def test_probe_does_not_run_on_non_windows():
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("nvidia-smi must not run outside Windows")

    report = compat.probe_cuda_12_8_driver_compatibility(
        platform_name="posix",
        run=unexpected_run,
    )
    assert report["status"] == "not_windows"


def test_probe_reports_missing_nvidia_smi_without_crashing():
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("nvidia-smi")

    report = compat.probe_cuda_12_8_driver_compatibility(
        platform_name="nt",
        run=missing,
    )
    assert report["status"] == "nvidia_smi_unavailable"


def test_warning_explains_cuda_scope_and_keeps_vulkan_engines_independent():
    report = compat.classify_cuda_12_8_driver_compatibility([{
        "name": "NVIDIA GeForce GTX 1660 Ti",
        "driver_version": "451.67",
    }])
    message, colour = compat.format_cuda_driver_status(report)
    assert "PyTorch CUDA 12.8" in message
    assert "V2 ยังใช้ได้" in message
    assert "Native Vulkan AI 4 ตัวไม่ถูกปิด" in message
    assert colour == "#FF7777"


def test_app_displays_driver_hint_as_a_separate_nonblocking_status_row():
    root = Path(__file__).resolve().parents[1]
    source = (root / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert "self._start_cuda_driver_compatibility_probe()" in source
    assert 'self._events.put(("cuda_compatibility", report))' in source
    assert 'elif kind == "cuda_compatibility":' in source
    assert "self.runtime_warning_label" in source
    assert "threading.Thread(" in source
