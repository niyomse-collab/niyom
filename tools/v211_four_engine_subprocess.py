"""Subprocess adapters for the four real V2.1.1 enhancement engines.

No models are bundled. Each engine must be independently installed and
licensed; subprocess invocation does not prove image quality.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
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

        processors[engine] = process
    return processors
