"""Run actual four-engine subprocess inference; never substitute mocks.

Requires a separately provisioned, SHA256-pinned manifest and a real PNG input.
Outputs and report stay local or in a private CI artifact, not the repository.
A passing run proves execution, NOT visual improvement over approved V2.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import os
import inspect

from PIL import Image

from tools.v211_four_engine_subprocess import ENGINES, make_processors
from tools.v211_gpu_process_telemetry import NvmlProcessProbe

NCNN_VULKAN_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")
from tools.v211_real_engine_manifest import load_real_engine_manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _classify_engine_failure(
    exc: Exception,
    process_record: dict | None = None,
) -> tuple[str, bool]:
    """Separate host Vulkan blocks from native crashes and output regressions.

    Windows STATUS_ACCESS_VIOLATION (0xC0000005) takes precedence over Vulkan
    text in stderr: the process crashed, so it is not safely retryable as only
    a missing-host-Vulkan condition. Preserve the exit code in the private-safe
    process record so the two failure modes remain distinguishable.
    """
    if isinstance(exc, InterruptedError):
        return "cancelled", False
    if isinstance(exc, TimeoutError):
        return "timeout", False
    if isinstance(exc, FileNotFoundError):
        return "executable_missing", False
    exit_code = process_record.get("exit_code") if isinstance(process_record, dict) else None
    message = str(exc).lower()
    explicit_vulkan_error = any(token in message for token in (
        # A generic "invalid gpu device" can indicate a bad CLI index or
        # adapter-binding regression. Only explicit Vulkan loader/device
        # initialization failures are retryable host limitations.
        "vkcreateinstance failed",
        "vulkan unavailable",
        "no vulkan device",
        "vulkan device not found",
    ))
    if (
        isinstance(exit_code, int)
        and not isinstance(exit_code, bool)
        and (exit_code & 0xFFFFFFFF) == 0xC0000005
    ):
        # Preserve the access violation as a distinct observed failure. When
        # explicit Vulkan initialization text is also present, classify it as
        # a host-limited compound failure and retry only on a Vulkan-capable host.
        if explicit_vulkan_error:
            return "vulkan_initialization_failed_with_access_violation", True
        return "windows_access_violation", False
    if explicit_vulkan_error:
        return "vulkan_initialization_failed", True
    return "subprocess_or_candidate_failure", False


def _option_value(argv: tuple[str, ...], flags: tuple[str, ...]) -> str | None:
    for index, token in enumerate(argv[:-1]):
        if token in flags:
            return argv[index + 1]
    return None


def _configured_device_selection(engine: str, command) -> dict | None:
    """Describe only backend/index flags passed to the CLI; never claim adapter use."""
    argv = getattr(command, "argv", None)
    if not isinstance(argv, (tuple, list)) or not argv:
        return None
    args = tuple(str(item) for item in argv[1:])
    if engine in NCNN_VULKAN_ENGINES:
        raw_index = _option_value(args, ("-g", "--gpu"))
        try:
            device_index = int(raw_index) if raw_index is not None else None
        except (TypeError, ValueError):
            device_index = None
        return {
            "backend": "ncnn_vulkan",
            "device_index": device_index,
            "explicitly_configured": raw_index is not None and device_index is not None,
            "actual_adapter_verified": False,
        }
    raw_backend = _option_value(args, ("-p", "--processor"))
    raw_index = _option_value(args, ("-d", "--device"))
    try:
        device_index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        device_index = None
    return {
        "backend": raw_backend or "auto",
        "device_index": device_index,
        "explicitly_configured": (
            raw_backend in ("cuda", "opencl") and device_index is not None
        ),
        "actual_adapter_verified": False,
    }


def _safe_process_record(value: dict | None) -> dict | None:
    """Whitelist non-sensitive process facts; omit paths, argv and raw output."""
    if not isinstance(value, dict):
        return None
    allowed = (
        "status", "process_started", "pid", "exit_code",
        "process_elapsed_ms", "elapsed_ms_total", "failure_type",
        "runtime_device_use_verified", "runtime_device_process_count",
        "runtime_device_verified_process_count", "runtime_device_all_processes_verified",
        "runtime_device_sample_count", "runtime_device_probe_status",
        "runtime_device_probe_error_type", "runtime_device_probe_conflict",
        "runtime_adapter_name",
        "runtime_adapter_index", "runtime_adapter_backend_apis",
    )
    result = {key: value[key] for key in allowed if key in value}
    exit_code = value.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        result["exit_code_hex"] = f"0x{exit_code & 0xFFFFFFFF:08X}"
    return result


def _native_process_execution_verified(value: dict | None) -> bool:
    """Require an observed successful native process, not only a plausible PNG."""
    if not isinstance(value, dict):
        return False
    pid = value.get("pid")
    exit_code = value.get("exit_code")
    return (
        value.get("status") in ("process_succeeded", "output_ready")
        and value.get("process_started") is True
        and isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
        and isinstance(exit_code, int) and not isinstance(exit_code, bool)
        and exit_code == 0
    )


def _make_processors_with_telemetry(
    commands, execution_records: dict, runtime_device_probe=None
) -> dict:
    """Pass lifecycle and NVML PID telemetry; tolerate legacy test doubles."""
    try:
        parameters = inspect.signature(make_processors).parameters
        accepts_kwargs = any(
            item.kind == inspect.Parameter.VAR_KEYWORD
            for item in parameters.values()
        )
        kwargs = {}
        if "execution_records" in parameters or accepts_kwargs:
            kwargs["execution_records"] = execution_records
        if "runtime_device_probe" in parameters or accepts_kwargs:
            kwargs["runtime_device_probe"] = runtime_device_probe
        return make_processors(commands, **kwargs)
    except (TypeError, ValueError):
        return make_processors(commands)



def run(
    manifest: Path, source: Path, output_dir: Path, *, timeout_seconds: int | None = None
) -> dict:
    # A missing or untrusted installation must still leave a failure report.
    # Do not create output images or invoke any executable until all hashes pass.
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real_inference_report.json"
    runtime_probe = NvmlProcessProbe(target_name="gtx 1660 ti")
    try:
        commands = load_real_engine_manifest(manifest)
        if timeout_seconds is not None:
            if not 1 <= int(timeout_seconds) <= 1800:
                raise ValueError("timeout_seconds must be between 1 and 1800")
            commands = {
                name: replace(command, timeout_seconds=min(command.timeout_seconds, int(timeout_seconds)))
                for name, command in commands.items()
            }
        process_telemetry = {}
        processors = _make_processors_with_telemetry(
            commands, process_telemetry, runtime_device_probe=runtime_probe
        )
    except Exception as exc:
        runtime_probe.close()
        report_path.write_text(json.dumps({
            "real_inference_verified": False,
            "candidate_output_validation_complete": False,
            "native_process_execution_verified": False,
            "per_engine_native_process_execution_verified": {
                name: False for name in ENGINES
            },
            "quality_improvement_verified": False,
            "failed_stage": "manifest_preflight",
            "failure_type": type(exc).__name__,
            "engines": {},
        }, indent=2) + "\n", encoding="utf-8")
        raise
    report = {
        "real_inference_verified": False,
        "candidate_output_validation_complete": False,
        "native_process_execution_verified": False,
        "per_engine_native_process_execution_verified": {
            name: False for name in ENGINES
        },
        "quality_improvement_verified": False,
        "runtime_device_use_verified": False,
        "execution_evidence_scope": (
            "candidate output invariants plus separately recorded native process lifecycle; "
            "GPU adapter use requires independent runtime telemetry"
        ),
        "engines": {},
    }
    try:
        with Image.open(source) as img:
            if img.format != "PNG":
                raise ValueError("source must be PNG")
            img.verify()
        with Image.open(source) as img:
            source_size = img.size
            source_mode = img.mode
            if "transparency" in img.info and "A" not in img.getbands():
                raise ValueError("palette/tRNS PNG transparency requires RGBA conversion before QA")
            if source_mode not in ("RGB", "RGBA"):
                raise ValueError("source must be an 8-bit RGB/RGBA PNG for native engine QA")
            source_alpha = source_mode == "RGBA"
            source_icc = img.info.get("icc_profile")
            source_dpi = img.info.get("dpi")
            source_alpha_image = img.getchannel("A").copy() if source_alpha else None
        report["source_sha256"] = sha256(source)
        report["source_size"] = source_size
    except Exception as exc:
        report.update({
            "failed_stage": "source_preflight",
            "failure_type": type(exc).__name__,
        })
        runtime_probe.close()
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise
    # Always attempt all four independent executables. One missing Vulkan
    # driver on a CI runner must not hide results for the other three engines.
    # A failure is still a failing exit status and can never certify a release.
    report["failures"] = {}
    report["completed_engine_count"] = 0
    for engine in ENGINES:
        destination = output_dir / (engine + ".png")
        destination.unlink(missing_ok=True)
        try:
            processors[engine](source, destination)
            with Image.open(destination) as image:
                image.load()
                if image.format != "PNG" or image.size != tuple(d * 2 for d in source_size):
                    raise ValueError(engine + ": expected a valid exact 2x PNG")
                if image.mode != source_mode:
                    raise ValueError(engine + ": output colour mode or alpha presence differs from source")
                if source_alpha_image is not None:
                    expected_alpha = source_alpha_image.resize(image.size, Image.Resampling.LANCZOS)
                    if image.getchannel("A").tobytes() != expected_alpha.tobytes():
                        raise ValueError(engine + ": alpha pixels differ from original cutout")
                output_icc = image.info.get("icc_profile")
                if output_icc != source_icc:
                    raise ValueError(engine + ": ICC profile presence or content differs from source")
                output_dpi = image.info.get("dpi")
                if source_dpi is None:
                    if output_dpi is not None:
                        raise ValueError(engine + ": engine introduced print DPI metadata")
                elif (output_dpi is None or len(output_dpi) != len(source_dpi)
                      or any(abs(float(a) - float(b)) > 0.1
                             for a, b in zip(source_dpi, output_dpi))):
                    raise ValueError(engine + ": print DPI changed or lost")
                process_record = _safe_process_record(process_telemetry.get(engine))
                native_process_verified = _native_process_execution_verified(process_record)
                report["engines"][engine] = {
                    "status": (
                        "native_process_and_2x_output_validated"
                        if native_process_verified
                        else "candidate_output_validated_without_process_evidence"
                    ),
                    "native_process_execution_verified": native_process_verified,
                    "process": process_record,
                    "device_configuration": _configured_device_selection(
                        engine, commands.get(engine)
                    ) if isinstance(commands, dict) else None,
                    "runtime_device_use_verified": bool(
                        process_record and process_record.get("runtime_device_use_verified") is True
                    ),
                    "runtime_device_telemetry": {
                        key: process_record.get(key)
                        for key in (
                            "runtime_device_probe_status",
                            "runtime_device_probe_conflict",
                            "runtime_device_process_count",
                            "runtime_device_verified_process_count",
                            "runtime_device_all_processes_verified",
                            "runtime_device_sample_count",
                            "runtime_adapter_name",
                            "runtime_adapter_index",
                            "runtime_adapter_backend_apis",
                        )
                        if process_record and key in process_record
                    },
                    "sha256": sha256(destination),
                    "size": list(image.size),
                    "mode": image.mode,
                    "alpha_preserved": ("A" in image.getbands()) == source_alpha,
                    "alpha_pixels_match_source": (
                        True if source_alpha_image is not None else None
                    ),
                    "icc_preserved": output_icc == source_icc,
                    "dpi_preserved": (
                        output_dpi is None if source_dpi is None else output_dpi is not None
                    ),
                }
                report["completed_engine_count"] += 1
        except Exception as exc:
            destination.unlink(missing_ok=True)
            # Save only type and a bounded generic description. Windows error
            # stderr may contain local paths or other private information.
            failure_process_record = _safe_process_record(process_telemetry.get(engine))
            failure_class, retry_on_vulkan_host = _classify_engine_failure(
                exc, failure_process_record
            )
            failure = {
                "error_type": type(exc).__name__,
                "error_class": failure_class,
                "native_process_execution_verified": _native_process_execution_verified(
                    failure_process_record
                ),
                "process": failure_process_record,
                "device_configuration": _configured_device_selection(
                    engine, commands.get(engine)
                ) if isinstance(commands, dict) else None,
                "runtime_device_use_verified": bool(
                    process_telemetry.get(engine, {}).get("runtime_device_use_verified") is True
                ),
                "runtime_device_telemetry": {
                    key: process_telemetry.get(engine, {}).get(key)
                    for key in (
                        "runtime_device_probe_status",
                        "runtime_device_probe_conflict",
                        "runtime_device_process_count",
                        "runtime_device_verified_process_count",
                        "runtime_device_all_processes_verified",
                        "runtime_device_sample_count",
                        "runtime_adapter_name",
                        "runtime_adapter_index",
                        "runtime_adapter_backend_apis",
                    )
                    if key in process_telemetry.get(engine, {})
                },
            }
            if any(token in str(exc).lower() for token in (
                "vkcreateinstance failed",
                "vulkan unavailable",
                "no vulkan device",
                "vulkan device not found",
            )):
                failure["vulkan_error_observed"] = True
            if retry_on_vulkan_host:
                failure["retry_on_vulkan_capable_host"] = True
            # ONLY the public GitHub workflow's deliberately synthetic test
            # permits a short diagnostic excerpt to help debug CLI arguments.
            # All customer jobs keep raw stderr and local file paths private.
            if os.environ.get("NIYOMSIL_V211_SYNTHETIC_CI_DEBUG") == "1":
                failure["synthetic_test_diagnostic"] = str(exc)[-600:]
            report["failures"][engine] = failure
    report["candidate_output_validation_complete"] = (
        report["completed_engine_count"] == len(ENGINES)
    )
    report["per_engine_native_process_execution_verified"] = {
        name: bool(
            (
                report.get("engines", {}).get(name)
                or report.get("failures", {}).get(name)
                or {}
            ).get("native_process_execution_verified") is True
        )
        for name in ENGINES
    }
    report["native_process_execution_verified"] = all(
        report["per_engine_native_process_execution_verified"].values()
    )
    report["real_inference_verified"] = (
        report["candidate_output_validation_complete"]
        and report["native_process_execution_verified"]
    )
    report["per_engine_runtime_device_use_verified"] = {
        name: bool(
            (report.get("engines", {}).get(name) or {}).get("runtime_device_use_verified") is True
        )
        for name in ENGINES
    }
    report["runtime_device_use_verified"] = all(
        report["per_engine_runtime_device_use_verified"].values()
    )
    report["execution_evidence_scope"] = (
        "verified native process start/PID/zero-exit plus exact output invariants; "
        "live NVML PID-to-adapter visibility is reported separately and is required "
        "for GPU-use certification; this is not visual-quality or print certification"
    )
    runtime_probe.close()
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int)
    args = parser.parse_args()
    result = run(
        args.manifest, args.input, args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, indent=2))
    if not result["real_inference_verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
