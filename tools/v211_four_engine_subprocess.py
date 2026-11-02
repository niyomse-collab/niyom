"""Four-engine subprocess adapters for experimental V2.1.1 integration.

Each command is explicitly configured against independently licensed, installed
executables and checkpoints. No shell interpolation, downloads or bundled weights.
Commands must contain {input} and {output} placeholders as separate arguments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

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
    """Produce callbacks compatible with run_candidates; require all four engines."""
    if set(commands) != set(ENGINES):
        raise ValueError("exactly four configured engines are required")
    processors = {}
    for engine in ENGINES:
        spec = commands[engine]

        def process(source: Path, destination: Path, *, _spec=spec) -> None:
            source = Path(source).resolve(strict=True)
            destination = Path(destination).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            argv = [
                part.replace("{input}", str(source)).replace("{output}", str(destination))
                for part in _spec.argv
            ]
            try:
                subprocess.run(
                    argv, check=True, shell=False, timeout=_spec.timeout_seconds,
                    capture_output=True, text=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "engine exited with code " + str(exc.returncode) + ": "
                    + (exc.stderr or "")[-1000:]
                ) from exc
            if not destination.is_file() or destination.stat().st_size == 0:
                raise RuntimeError("engine produced no usable output")

        processors[engine] = process
    return processors
