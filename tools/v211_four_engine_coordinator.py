"""Experimental four-engine coordinator; no model binaries or weights bundled.

Each callable receives the ORIGINAL source and must produce a candidate at the
SAME requested dimensions. This module deliberately does not stack four upscales,
or pretend to judge perceptual quality without real A/B evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from PIL import Image

ENGINES = ("real_esrgan", "waifu2x", "real_cugan", "anime4k")


@dataclass(frozen=True)
class Candidate:
    engine: str
    path: Path
    width: int
    height: int


def validate_candidate(source: Path, candidate: Path, target_size: tuple[int, int]) -> None:
    """Fail closed on dimensions, alpha/ICC loss, and changed pixel mode."""
    with Image.open(source) as original, Image.open(candidate) as output:
        if output.size != target_size:
            raise ValueError("candidate dimensions differ from target")
        if original.mode not in ("RGB", "RGBA") or output.mode != original.mode:
            raise ValueError("candidate changed image mode or transparency")
        if original.info.get("icc_profile") != output.info.get("icc_profile"):
            raise ValueError("candidate lost or altered ICC profile")
        if original.mode == "RGBA":
            # All engines must preserve the original cutout rather than invent alpha.
            # Compare at output resolution: downsampling an upscaled alpha back to
            # source resolution can conceal fringe and transparency corruption.
            expected_alpha = original.getchannel("A").resize(
                target_size, resample=Image.Resampling.LANCZOS
            )
            actual_alpha = output.getchannel("A")
            if actual_alpha.tobytes() != expected_alpha.tobytes():
                raise ValueError(
                    "RGBA alpha differs from source resized with LANCZOS; "
                    "engine output cannot be used without alpha restoration"
                )


def run_candidates(
    source: Path,
    output_dir: Path,
    target_size: tuple[int, int],
    processors: Mapping[str, Callable[[Path, Path], None]],
) -> dict[str, object]:
    """Run every engine candidate in a bounded, sequential research pass.

    Callbacks are externally configured and independently licensed. No fused
    production image is returned until fusion and quality gates are implemented.
    """
    source = Path(source)
    output_dir = Path(output_dir)
    if not source.is_file() or min(target_size) <= 0:
        raise ValueError("missing source or invalid target size")
    missing = set(ENGINES) - set(processors)
    if missing:
        raise ValueError("four engines required: " + ", ".join(sorted(missing)))
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Candidate] = []
    failures: dict[str, str] = {}
    for name in ENGINES:
        destination = output_dir / (name + ".png")
        try:
            processors[name](source, destination)
            if not destination.is_file():
                raise RuntimeError("processor produced no output")
            validate_candidate(source, destination, target_size)
            candidates.append(Candidate(name, destination, *target_size))
        except Exception as exc:
            failures[name] = type(exc).__name__ + ": " + str(exc)
            destination.unlink(missing_ok=True)
    return {
        "research_only": True,
        "fusion_implemented": False,
        "quality_certified": False,
        "candidates": candidates,
        "failures": failures,
        "ready_for_fusion_research": len(candidates) == len(ENGINES),
    }
