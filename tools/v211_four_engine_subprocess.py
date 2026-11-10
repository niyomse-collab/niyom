"""Subprocess adapters for the four real V2.1.1 enhancement engines.

No models are bundled. Each engine must be independently installed and
licensed; subprocess invocation does not prove image quality.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import os
import signal
import tempfile
import time
from typing import Callable, Mapping, MutableMapping

from PIL import Image

ENGINES = ("real_esrgan", "waifu2x", "real_cugan", "anime4k")


@dataclass(frozen=True)
class EngineCommand:
    argv: tuple[str, ...]
    timeout_seconds: int = 1800

    def __post_init__(self) -> None:
        if not self.argv or self.timeout_seconds <= 0:
            raise ValueError("invalid engine command")
        if not any("{input}" in arg for arg in self.argv):
            raise ValueError("missing input placeholder")
        if not any("{output}" in arg for arg in self.argv):
            raise ValueError("missing output placeholder")


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Stop the active native engine and its children before returning to V2."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        # NCNN wrappers may spawn a Vulkan child. taskkill /T prevents it from
        # continuing to use the GPU after the user cancels the parent process.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                process.terminate()
            except OSError:
                pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def make_processors(
    commands: Mapping[str, EngineCommand],
    *,
    cancel_check: Callable[[], bool] | None = None,
    pre_launch_check: Callable[[str], dict] | None = None,
    execution_records: MutableMapping[str, dict] | None = None,
    runtime_device_probe: Callable[[int, str], dict] | None = None,
):
    """Make engine callbacks, failing closed when any engine is unconfigured.

    Optional execution_records receives process lifecycle and allowlisted
    runtime-adapter facts only. It never stores command arguments, source/output
    paths, stdout, stderr or image data. A missing/unavailable probe is unverified.
    """
    if set(commands) != set(ENGINES):
        raise ValueError("exactly four configured engines are required")
    processors = {}
    for engine in ENGINES:
        spec = commands[engine]

        def process(
            source: Path,
            destination: Path,
            *,
            _spec=spec,
            _engine=engine,
        ) -> None:
            previous_record = execution_records.get(_engine, {}) if execution_records is not None else {}
            previous_checks = previous_record.get("pre_launch_vram_checks", 0)
            previous_minimum = previous_record.get("pre_launch_vram_min_free_mib")
            previous_runtime_process_count = previous_record.get("runtime_device_process_count", 0)
            previous_runtime_verified_count = previous_record.get("runtime_device_verified_process_count", 0)
            previous_runtime_sample_count = previous_record.get("runtime_device_sample_count", 0)
            previous_nvml_memory_count = previous_record.get(
                "runtime_device_nvml_memory_verified_process_count", 0
            )
            previous_wddm_pdh_count = previous_record.get(
                "runtime_device_wddm_pdh_verified_process_count", 0
            )
            previous_gpu_min_samples = previous_record.get("runtime_gpu_engine_min_sample_count")
            previous_gpu_min_active = previous_record.get("runtime_gpu_engine_min_active_sample_count")
            previous_gpu_max_utilization = previous_record.get("runtime_gpu_engine_max_utilization_percent")
            previous_gpu_luid_match = previous_record.get("runtime_gpu_engine_adapter_luid_match")
            previous_gpu_luid = previous_record.get("runtime_gpu_engine_adapter_luid")
            if previous_wddm_pdh_count == 0:
                previous_gpu_luid_match = False
                previous_gpu_luid = None
            elif not (
                previous_gpu_luid_match is True
                and isinstance(previous_gpu_luid, str)
                and len(previous_gpu_luid) == 21
                and previous_gpu_luid[:2] == "0x"
                and previous_gpu_luid[10:13] == "_0x"
                and all(ch in "0123456789abcdef" for ch in (
                    previous_gpu_luid[2:10] + previous_gpu_luid[13:21]
                ))
            ):
                previous_gpu_luid_match = False
                previous_gpu_luid = None
            for value_name, value in (
                ("runtime_device_process_count", previous_runtime_process_count),
                ("runtime_device_verified_process_count", previous_runtime_verified_count),
                ("runtime_device_sample_count", previous_runtime_sample_count),
                ("runtime_device_nvml_memory_verified_process_count", previous_nvml_memory_count),
                ("runtime_device_wddm_pdh_verified_process_count", previous_wddm_pdh_count),
            ):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    if value_name == "runtime_device_process_count":
                        previous_runtime_process_count = 0
                    elif value_name == "runtime_device_verified_process_count":
                        previous_runtime_verified_count = 0
                    elif value_name == "runtime_device_sample_count":
                        previous_runtime_sample_count = 0
                    elif value_name == "runtime_device_nvml_memory_verified_process_count":
                        previous_nvml_memory_count = 0
                    else:
                        previous_wddm_pdh_count = 0
            if (
                isinstance(previous_gpu_min_samples, bool)
                or not isinstance(previous_gpu_min_samples, int)
                or previous_gpu_min_samples < 2
            ):
                previous_gpu_min_samples = None
            if (
                isinstance(previous_gpu_min_active, bool)
                or not isinstance(previous_gpu_min_active, int)
                or previous_gpu_min_active < 1
            ):
                previous_gpu_min_active = None
            if (
                isinstance(previous_gpu_max_utilization, bool)
                or not isinstance(previous_gpu_max_utilization, (int, float))
                or previous_gpu_max_utilization <= 0
            ):
                previous_gpu_max_utilization = None
            previous_runtime_all_verified = previous_record.get(
                "runtime_device_all_processes_verified",
                previous_runtime_process_count == 0,
            )
            if not isinstance(previous_runtime_all_verified, bool):
                previous_runtime_all_verified = previous_runtime_process_count == 0
            if previous_wddm_pdh_count > 0 and previous_gpu_luid_match is not True:
                previous_runtime_all_verified = False
            record = {
                "status": "not_started",
                "process_started": False,
                "pid": None,
                "exit_code": None,
                "pre_launch_vram_checks": (
                    previous_checks if isinstance(previous_checks, int)
                    and not isinstance(previous_checks, bool) and previous_checks >= 0 else 0
                ),
                "runtime_device_use_verified": False,
                "runtime_device_process_count": previous_runtime_process_count,
                "runtime_device_verified_process_count": previous_runtime_verified_count,
                "runtime_device_all_processes_verified": previous_runtime_all_verified,
                "runtime_device_sample_count": previous_runtime_sample_count,
                "runtime_device_nvml_memory_verified_process_count": previous_nvml_memory_count,
                "runtime_device_wddm_pdh_verified_process_count": previous_wddm_pdh_count,
                "runtime_device_evidence_source": (
                    "mixed" if previous_nvml_memory_count and previous_wddm_pdh_count
                    else "nvml_process_memory" if previous_nvml_memory_count
                    else "nvml_pid_plus_windows_gpu_engine_pdh" if previous_wddm_pdh_count
                    else None
                ),
                "runtime_gpu_engine_min_sample_count": previous_gpu_min_samples,
                "runtime_gpu_engine_min_active_sample_count": previous_gpu_min_active,
                "runtime_gpu_engine_max_utilization_percent": previous_gpu_max_utilization,
                "runtime_gpu_engine_adapter_luid_match": previous_gpu_luid_match,
                "runtime_gpu_engine_adapter_luid": previous_gpu_luid,
                "runtime_device_probe_status": (
                    "not_configured" if runtime_device_probe is None else "not_observed"
                ),
                "runtime_device_probe_conflict": False,
            }
            if isinstance(previous_minimum, int) and not isinstance(previous_minimum, bool) and previous_minimum >= 0:
                record["pre_launch_vram_min_free_mib"] = previous_minimum
            if execution_records is not None:
                execution_records[_engine] = record
            total_started = time.monotonic()
            process_started = None
            process_handle = None
            runtime_verified_this_process = False
            runtime_probe_conflict = False
            runtime_sample_count_this_process = 0
            runtime_evidence_source_this_process = None
            runtime_gpu_engine_samples_this_process = 0
            runtime_gpu_engine_active_this_process = 0
            runtime_gpu_engine_max_this_process = 0.0
            runtime_gpu_engine_luid_match_this_process = False
            runtime_gpu_engine_luid_this_process = None

            def sample_runtime_device():
                nonlocal runtime_verified_this_process, runtime_probe_conflict, runtime_sample_count_this_process
                nonlocal runtime_evidence_source_this_process
                nonlocal runtime_gpu_engine_samples_this_process
                nonlocal runtime_gpu_engine_active_this_process
                nonlocal runtime_gpu_engine_max_this_process
                nonlocal runtime_gpu_engine_luid_match_this_process
                nonlocal runtime_gpu_engine_luid_this_process
                if runtime_device_probe is None:
                    return
                pid = record.get("pid")
                if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                    return
                try:
                    evidence = runtime_device_probe(pid, _engine)
                except Exception as exc:
                    record["runtime_device_probe_status"] = "probe_error"
                    record["runtime_device_probe_error_type"] = type(exc).__name__
                    return
                if not isinstance(evidence, dict):
                    record["runtime_device_probe_status"] = "invalid_probe_result"
                    return
                runtime_sample_count_this_process += 1
                record["runtime_device_sample_count"] += 1
                status = evidence.get("status")
                status = status[:48] if isinstance(status, str) else "unclassified"
                if evidence.get("verified") is True and not runtime_probe_conflict:
                    runtime_verified_this_process = True
                    record["runtime_device_probe_status"] = "verified"
                    record["runtime_adapter_name"] = str(
                        evidence.get("adapter_name") or ""
                    )[:160]
                    adapter_index = evidence.get("adapter_index")
                    if (
                        isinstance(adapter_index, int)
                        and not isinstance(adapter_index, bool)
                        and adapter_index >= 0
                    ):
                        record["runtime_adapter_index"] = adapter_index
                    backend_apis = evidence.get("backend_apis")
                    if isinstance(backend_apis, list):
                        record["runtime_adapter_backend_apis"] = [
                            str(item)[:24] for item in backend_apis[:4]
                            if isinstance(item, str)
                        ]
                    evidence_source = evidence.get("evidence_source")
                    if evidence_source in (
                        "nvml_process_memory",
                        "nvml_pid_plus_windows_gpu_engine_pdh",
                    ):
                        runtime_evidence_source_this_process = evidence_source
                    gpu_samples = evidence.get("gpu_engine_sample_count")
                    gpu_active = evidence.get("gpu_engine_active_sample_count")
                    gpu_max = evidence.get("gpu_engine_max_utilization_percent")
                    if (
                        isinstance(gpu_samples, int) and not isinstance(gpu_samples, bool)
                        and gpu_samples >= 2
                    ):
                        runtime_gpu_engine_samples_this_process = gpu_samples
                    if (
                        isinstance(gpu_active, int) and not isinstance(gpu_active, bool)
                        and gpu_active >= 1
                    ):
                        runtime_gpu_engine_active_this_process = gpu_active
                    if (
                        isinstance(gpu_max, (int, float)) and not isinstance(gpu_max, bool)
                        and gpu_max > 0
                    ):
                        runtime_gpu_engine_max_this_process = float(gpu_max)
                    gpu_luid_match = evidence.get("gpu_engine_adapter_luid_match")
                    gpu_luid = evidence.get("gpu_engine_adapter_luid")
                    if (
                        evidence_source == "nvml_pid_plus_windows_gpu_engine_pdh"
                        and gpu_luid_match is True
                        and isinstance(gpu_luid, str)
                        and len(gpu_luid) == 21
                        and gpu_luid[:2] == "0x"
                        and gpu_luid[10:13] == "_0x"
                        and all(ch in "0123456789abcdef" for ch in (
                            gpu_luid[2:10] + gpu_luid[13:21]
                        ))
                    ):
                        runtime_gpu_engine_luid_match_this_process = True
                        runtime_gpu_engine_luid_this_process = gpu_luid.lower()
                elif status in (
                    "pid_seen_on_wrong_adapter",
                    "pid_seen_on_multiple_adapters",
                    "target_adapter_ambiguous",
                    "target_adapter_missing",
                ):
                    runtime_probe_conflict = True
                    runtime_verified_this_process = False
                    record["runtime_device_probe_conflict"] = True
                    record["runtime_device_probe_status"] = status
                elif not runtime_verified_this_process:
                    record["runtime_device_probe_status"] = status

            source = Path(source).resolve(strict=True)
            destination = Path(destination).resolve()
            try:
                if source == destination:
                    raise ValueError("engine output must not overwrite its source")
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Never accept a stale output from an earlier attempt.
                destination.unlink(missing_ok=True)
                if cancel_check and cancel_check():
                    record["status"] = "cancelled_before_launch"
                    raise InterruptedError("Processing stopped by user")
                argv = [
                    part.replace("{input}", str(source)).replace("{output}", str(destination))
                    for part in _spec.argv
                ]
                launch = {
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                    "text": True,
                    "shell": False,
                    "cwd": str(Path(argv[0]).resolve().parent),
                }
                if os.name == "nt":
                    launch["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                else:
                    # A separate session lets cancellation terminate the whole
                    # native process group rather than leaving Vulkan children.
                    launch["start_new_session"] = True
                if pre_launch_check is not None:
                    record["pre_launch_vram_checks"] += 1
                    record["status"] = "preflight_check"
                    try:
                        snapshot = pre_launch_check(_engine)
                        if not isinstance(snapshot, dict) or snapshot.get("passed") is not True:
                            raise RuntimeError("per-process VRAM preflight did not pass")
                        total = snapshot.get("total_mib")
                        free = snapshot.get("free_mib")
                        minimum = snapshot.get("minimum_free_mib")
                        if (
                            isinstance(total, bool) or not isinstance(total, int) or total <= 0
                            or isinstance(free, bool) or not isinstance(free, int)
                            or free < 0 or free > total
                            or isinstance(minimum, bool) or not isinstance(minimum, int)
                            or minimum < 1 or free < minimum
                        ):
                            raise RuntimeError("per-process VRAM snapshot is invalid or below threshold")
                    except Exception as exc:
                        record["status"] = "preflight_failed"
                        record["failure_type"] = type(exc).__name__
                        raise
                    record["pre_launch_vram"] = {
                        "passed": True,
                        "free_mib": free,
                        "minimum_free_mib": minimum,
                    }
                    previous_minimum = record.get("pre_launch_vram_min_free_mib")
                    record["pre_launch_vram_min_free_mib"] = (
                        free if not isinstance(previous_minimum, int)
                        else min(previous_minimum, free)
                    )
                    record["status"] = "preflight_passed"
                process_started = time.monotonic()
                process_handle = subprocess.Popen(argv, **launch)
                record["process_started"] = True
                try:
                    record["pid"] = int(process_handle.pid)
                except (AttributeError, TypeError, ValueError):
                    record["pid"] = None
                record["status"] = "running"
                sample_runtime_device()
                deadline = process_started + _spec.timeout_seconds
                while True:
                    if cancel_check and cancel_check():
                        _terminate_process_tree(process_handle)
                        process_handle.communicate()
                        record["exit_code"] = process_handle.returncode
                        record["process_elapsed_ms"] = int(
                            (time.monotonic() - process_started) * 1000
                        )
                        record["status"] = "cancelled"
                        raise InterruptedError("Processing stopped by user")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _terminate_process_tree(process_handle)
                        process_handle.communicate()
                        record["exit_code"] = process_handle.returncode
                        record["process_elapsed_ms"] = int(
                            (time.monotonic() - process_started) * 1000
                        )
                        record["status"] = "timed_out"
                        raise TimeoutError("engine timed out")
                    try:
                        stdout, stderr = process_handle.communicate(
                            timeout=min(
                                0.05 if runtime_device_probe is not None else 0.2,
                                remaining,
                            )
                        )
                        break
                    except subprocess.TimeoutExpired:
                        sample_runtime_device()
                        continue
                record["exit_code"] = (
                    int(process_handle.returncode)
                    if process_handle.returncode is not None else None
                )
                record["process_elapsed_ms"] = int(
                    (time.monotonic() - process_started) * 1000
                )
                if process_handle.returncode != 0:
                    record["status"] = "process_failed"
                    raise RuntimeError(
                        "engine exited with code " + str(process_handle.returncode) + ": "
                        + (stderr or stdout or "")[-1000:]
                    )
                record["status"] = "process_succeeded"

                if cancel_check and cancel_check():
                    destination.unlink(missing_ok=True)
                    record["status"] = "cancelled"
                    raise InterruptedError("Processing stopped by user")
                if not destination.is_file() or destination.stat().st_size == 0:
                    destination.unlink(missing_ok=True)
                    raise RuntimeError("engine produced no usable output")
                # Preserve print metadata without changing image pixels. An external
                # engine may drop PNG ICC/DPI even when its inference is valid.
                # A conflicting ICC is never overwritten: the coordinator rejects it.
                with Image.open(source) as original, Image.open(destination) as output:
                    source_icc = original.info.get("icc_profile")
                    output_icc = output.info.get("icc_profile")
                    source_dpi = original.info.get("dpi")
                    output_dpi = output.info.get("dpi")
                    restore_icc = bool(source_icc and not output_icc)
                    restore_dpi = source_dpi is not None and output_dpi is None
                    # NCNN/Vulkan upscalers often discard the alpha channel.
                    # Rebuild it from the ORIGINAL cutout, never the inferred pixels.
                    restore_alpha = original.mode == "RGBA"
                    if restore_alpha and output.mode not in ("RGB", "RGBA"):
                        raise ValueError("RGBA input requires RGB/RGBA engine output")
                    if restore_alpha or restore_icc or restore_dpi:
                        if destination.suffix.lower() != ".png":
                            raise ValueError("print metadata/alpha restoration requires PNG engine output")
                        output.load()
                        restored = output.copy()
                        if restore_alpha:
                            source_alpha = original.getchannel("A").resize(
                                output.size, resample=Image.Resampling.LANCZOS
                            )
                            restored = restored.convert("RGBA")
                            restored.putalpha(source_alpha)
                        fd, temp_name = tempfile.mkstemp(
                            prefix=".v211_metadata_", suffix=".png", dir=destination.parent
                        )
                        os.close(fd)
                        temp_path = Path(temp_name)
                        try:
                            options = {}
                            if source_icc and (restore_icc or output_icc):
                                options["icc_profile"] = source_icc if restore_icc else output_icc
                            if restore_dpi:
                                options["dpi"] = source_dpi
                            elif output_dpi is not None:
                                options["dpi"] = output_dpi
                            restored.save(temp_path, format="PNG", **options)
                            os.replace(temp_path, destination)
                        finally:
                            temp_path.unlink(missing_ok=True)
                if cancel_check and cancel_check():
                    destination.unlink(missing_ok=True)
                    record["status"] = "cancelled"
                    raise InterruptedError("Processing stopped by user")
                record["status"] = "output_ready"
            except InterruptedError:
                destination.unlink(missing_ok=True)
                if record["status"] in ("not_started", "running"):
                    record["status"] = "cancelled"
                record["failure_type"] = "InterruptedError"
                raise
            except TimeoutError:
                destination.unlink(missing_ok=True)
                record["status"] = "timed_out"
                record["failure_type"] = "TimeoutError"
                raise
            except BaseException as exc:
                destination.unlink(missing_ok=True)
                if process_handle is not None and record["exit_code"] is None:
                    try:
                        observed_code = process_handle.poll()
                        if observed_code is not None:
                            record["exit_code"] = int(observed_code)
                    except (AttributeError, TypeError, ValueError):
                        pass
                if record["status"] in ("not_started", "running"):
                    record["status"] = (
                        "process_failed" if record["process_started"] else "launch_failed"
                    )
                record["failure_type"] = type(exc).__name__
                raise
            finally:
                if process_handle is not None and process_started is not None:
                    if (
                        runtime_verified_this_process
                        and runtime_evidence_source_this_process
                        == "nvml_pid_plus_windows_gpu_engine_pdh"
                    ):
                        if not runtime_gpu_engine_luid_match_this_process:
                            runtime_verified_this_process = False
                            runtime_probe_conflict = True
                            record["runtime_device_probe_conflict"] = True
                            record["runtime_device_probe_status"] = "gpu_engine_luid_unverified"
                        elif (
                            previous_gpu_luid is not None
                            and previous_gpu_luid != runtime_gpu_engine_luid_this_process
                        ):
                            runtime_verified_this_process = False
                            runtime_probe_conflict = True
                            record["runtime_device_probe_conflict"] = True
                            record["runtime_device_probe_status"] = "gpu_engine_luid_changed"
                    record["runtime_device_process_count"] = previous_runtime_process_count + 1
                    record["runtime_device_verified_process_count"] = (
                        previous_runtime_verified_count + int(runtime_verified_this_process)
                    )
                    all_runtime_processes_verified = (
                        previous_runtime_all_verified
                        and runtime_verified_this_process
                        and not runtime_probe_conflict
                    )
                    record["runtime_device_all_processes_verified"] = (
                        all_runtime_processes_verified
                    )
                    record["runtime_device_use_verified"] = bool(
                        record["runtime_device_process_count"] > 0
                        and all_runtime_processes_verified
                    )
                    if runtime_verified_this_process:
                        if runtime_evidence_source_this_process == "nvml_process_memory":
                            record["runtime_device_nvml_memory_verified_process_count"] += 1
                        elif runtime_evidence_source_this_process == "nvml_pid_plus_windows_gpu_engine_pdh":
                            record["runtime_device_wddm_pdh_verified_process_count"] += 1
                            old_min_samples = record.get("runtime_gpu_engine_min_sample_count")
                            old_min_active = record.get("runtime_gpu_engine_min_active_sample_count")
                            record["runtime_gpu_engine_min_sample_count"] = (
                                runtime_gpu_engine_samples_this_process
                                if old_min_samples is None
                                else min(old_min_samples, runtime_gpu_engine_samples_this_process)
                            )
                            record["runtime_gpu_engine_min_active_sample_count"] = (
                                runtime_gpu_engine_active_this_process
                                if old_min_active is None
                                else min(old_min_active, runtime_gpu_engine_active_this_process)
                            )
                            old_max = record.get("runtime_gpu_engine_max_utilization_percent")
                            record["runtime_gpu_engine_max_utilization_percent"] = max(
                                float(old_max or 0.0), runtime_gpu_engine_max_this_process
                            )
                            record["runtime_gpu_engine_adapter_luid_match"] = True
                            record["runtime_gpu_engine_adapter_luid"] = (
                                runtime_gpu_engine_luid_this_process
                            )
                    memory_count = record["runtime_device_nvml_memory_verified_process_count"]
                    wddm_count = record["runtime_device_wddm_pdh_verified_process_count"]
                    record["runtime_device_evidence_source"] = (
                        "mixed" if memory_count and wddm_count
                        else "nvml_process_memory" if memory_count
                        else "nvml_pid_plus_windows_gpu_engine_pdh" if wddm_count
                        else None
                    )
                    if runtime_device_probe is None:
                        record["runtime_device_probe_status"] = "not_configured"
                    elif not runtime_verified_this_process and record.get(
                        "runtime_device_probe_status"
                    ) == "not_observed":
                        record["runtime_device_probe_status"] = "pid_not_observed"
                record["elapsed_ms_total"] = int(
                    (time.monotonic() - total_started) * 1000
                )
                if process_handle is not None and runtime_device_probe is not None:
                    close_pid = getattr(runtime_device_probe, "close_pid", None)
                    if callable(close_pid):
                        try:
                            close_pid(record.get("pid"))
                        except Exception:
                            pass

        processors[engine] = process
    return processors
