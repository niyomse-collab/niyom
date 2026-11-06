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

from PIL import Image

from tools.v211_four_engine_subprocess import ENGINES, make_processors

NCNN_VULKAN_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")
from tools.v211_real_engine_manifest import load_real_engine_manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _classify_engine_failure(exc: Exception) -> tuple[str, bool]:
    """Separate Vulkan host initialization blocks from engine/output regressions.

    A Vulkan initialization error is environment-dependent: it must be retried
    on a host with a working Vulkan loader/device. It is not evidence of model
    quality and must never be counted as successful inference.
    """
    if isinstance(exc, InterruptedError):
        return "cancelled", False
    if isinstance(exc, TimeoutError):
        return "timeout", False
    if isinstance(exc, FileNotFoundError):
        return "executable_missing", False
    message = str(exc).lower()
    if any(token in message for token in (
        "vkcreateinstance failed",
        "invalid gpu device",
        "vulkan unavailable",
        "no vulkan device",
        "vulkan device not found",
    )):
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
    )
    return {key: value[key] for key in allowed if key in value}



def run(
    manifest: Path, source: Path, output_dir: Path, *, timeout_seconds: int | None = None
) -> dict:
    # A missing or untrusted installation must still leave a failure report.
    # Do not create output images or invoke any executable until all hashes pass.
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real_inference_report.json"
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
        processors = make_processors(commands, execution_records=process_telemetry)
    except Exception as exc:
        report_path.write_text(json.dumps({
            "real_inference_verified": False,
            "quality_improvement_verified": False,
            "failed_stage": "manifest_preflight",
            "failure_type": type(exc).__name__,
            "engines": {},
        }, indent=2) + "\n", encoding="utf-8")
        raise
    report = {
        "real_inference_verified": False,
        "quality_improvement_verified": False,
        "runtime_device_use_verified": False,
        "execution_evidence_scope": (
            "native process launch/exit, configured CLI backend/index and output invariants only"
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
            if "transparency" in img.info and "A" not in img.getbands():
                raise ValueError("palette/tRNS PNG transparency requires RGBA conversion before QA")
            source_alpha = "A" in img.getbands()
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
                if image.mode not in ("RGB", "RGBA"):
                    raise ValueError(engine + ": invalid colour mode")
                if source_alpha and "A" not in image.getbands():
                    raise ValueError(engine + ": alpha channel lost")
                if source_alpha_image is not None:
                    expected_alpha = source_alpha_image.resize(image.size, Image.Resampling.LANCZOS)
                    if image.getchannel("A").tobytes() != expected_alpha.tobytes():
                        raise ValueError(engine + ": alpha pixels differ from original cutout")
                if source_icc and image.info.get("icc_profile") != source_icc:
                    raise ValueError(engine + ": ICC changed or lost")
                output_dpi = image.info.get("dpi")
                if source_dpi is not None and (output_dpi is None or
                    len(output_dpi) != len(source_dpi) or
                    any(abs(float(a) - float(b)) > 0.1 for a, b in zip(source_dpi, output_dpi))):
                    raise ValueError(engine + ": print DPI changed or lost")
                process_record = _safe_process_record(process_telemetry.get(engine))
                report["engines"][engine] = {
                    "status": "binary_executed_and_2x_output_validated",
                    "process": process_record,
                    "device_configuration": _configured_device_selection(
                        engine, commands.get(engine)
                    ) if isinstance(commands, dict) else None,
                    "runtime_device_use_verified": False,
                    "sha256": sha256(destination),
                    "size": list(image.size),
                    "mode": image.mode,
                    "alpha_preserved": not source_alpha or "A" in image.getbands(),
                    "alpha_pixels_match_source": source_alpha_image is not None,
                    "icc_preserved": not source_icc or image.info.get("icc_profile") == source_icc,
                    "dpi_preserved": source_dpi is None or output_dpi is not None,
                }
                report["completed_engine_count"] += 1
        except Exception as exc:
            destination.unlink(missing_ok=True)
            # Save only type and a bounded generic description. Windows error
            # stderr may contain local paths or other private information.
            failure_class, retry_on_vulkan_host = _classify_engine_failure(exc)
            failure = {
                "error_type": type(exc).__name__,
                "error_class": failure_class,
                "process": _safe_process_record(process_telemetry.get(engine)),
                "device_configuration": _configured_device_selection(
                    engine, commands.get(engine)
                ) if isinstance(commands, dict) else None,
                "runtime_device_use_verified": False,
            }
            if retry_on_vulkan_host:
                failure["retry_on_vulkan_capable_host"] = True
            # ONLY the public GitHub workflow's deliberately synthetic test
            # permits a short diagnostic excerpt to help debug CLI arguments.
            # All customer jobs keep raw stderr and local file paths private.
            if os.environ.get("NIYOMSIL_V211_SYNTHETIC_CI_DEBUG") == "1":
                failure["synthetic_test_diagnostic"] = str(exc)[-600:]
            report["failures"][engine] = failure
    report["real_inference_verified"] = report["completed_engine_count"] == len(ENGINES)
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
