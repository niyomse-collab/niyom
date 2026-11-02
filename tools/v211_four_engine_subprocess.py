"""Subprocess adapters for the four real V2.1.1 enhancement engines.

No models are bundled. Each engine must be independently installed and
licensed; subprocess invocation does not prove image quality.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import os
import tempfile

from PIL import Image
from typing import Mapping

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


def make_processors(commands: Mapping[str, EngineCommand]):
    """Make engine callbacks, failing closed when any engine is unconfigured."""
    if set(commands) != set(ENGINES):
        raise ValueError("exactly four configured engines are required")
    processors = {}
    for engine in ENGINES:
        spec = commands[engine]

        def process(source: Path, destination: Path, *, _spec=spec) -> None:
            source = Path(source).resolve(strict=True)
            destination = Path(destination).resolve()
            if source == destination:
                raise ValueError("engine output must not overwrite its source")
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Prevent an earlier output from being mistaken for successful
            # inference if the executable exits 0 without writing a new file.
            destination.unlink(missing_ok=True)
            argv = [
                part.replace("{input}", str(source)).replace("{output}", str(destination))
                for part in _spec.argv
            ]
            try:
                subprocess.run(
                    argv, check=True, shell=False, timeout=_spec.timeout_seconds,
                    capture_output=True, text=True,
                )
            except subprocess.TimeoutExpired as exc:
                destination.unlink(missing_ok=True)
                raise RuntimeError("engine timed out") from exc
            except subprocess.CalledProcessError as exc:
                destination.unlink(missing_ok=True)
                raise RuntimeError(
                    "engine exited with code " + str(exc.returncode) + ": "
                    + (exc.stderr or "")[-1000:]
                ) from exc
            except OSError:
                destination.unlink(missing_ok=True)
                raise
            if not destination.is_file() or destination.stat().st_size == 0:
                destination.unlink(missing_ok=True)
                raise RuntimeError("engine produced no usable output")
            # External upscalers commonly strip ICC. Restore the source
            # profile only when missing, never overwrite a conflicting profile.
            # Coordinator still rejects changed mode or alpha.
            with Image.open(source) as original, Image.open(destination) as output:
                source_icc = original.info.get("icc_profile")
                output_icc = output.info.get("icc_profile")
                if source_icc and not output_icc:
                    if destination.suffix.lower() != ".png":
                        raise ValueError("ICC restoration requires PNG engine output")
                    output.load()
                    fd, temp_name = tempfile.mkstemp(
                        prefix=".v211_icc_", suffix=".png", dir=destination.parent
                    )
                    os.close(fd)
                    temp_path = Path(temp_name)
                    try:
                        options = {"icc_profile": source_icc}
                        if "dpi" in output.info:
                            options["dpi"] = output.info["dpi"]
                        output.save(temp_path, format="PNG", **options)
                        os.replace(temp_path, destination)
                    finally:
                        temp_path.unlink(missing_ok=True)

        processors[engine] = process
    return processors
