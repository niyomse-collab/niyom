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
    execution_records: MutableMapping[str, dict] | None = None,
):
    """Make engine callbacks, failing closed when any engine is unconfigured.

    Optional execution_records receives only process lifecycle facts. It never
    stores command arguments, source/output paths, stdout, stderr or image data.
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
            record = {
                "status": "not_started",
                "process_started": False,
                "pid": None,
                "exit_code": None,
            }
            if execution_records is not None:
                execution_records[_engine] = record
            total_started = time.monotonic()
            process_started = None
            process_handle = None
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
                process_started = time.monotonic()
                process_handle = subprocess.Popen(argv, **launch)
                record["process_started"] = True
                try:
                    record["pid"] = int(process_handle.pid)
                except (AttributeError, TypeError, ValueError):
                    record["pid"] = None
                record["status"] = "running"
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
                            timeout=min(0.2, remaining)
                        )
                        break
                    except subprocess.TimeoutExpired:
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
                record["elapsed_ms_total"] = int(
                    (time.monotonic() - total_started) * 1000
                )

        processors[engine] = process
    return processors
