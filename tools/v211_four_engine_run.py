"""Run the four configured AI engines on one image in the V2.1.1 research branch.

Default configuration requires installed real engine executables and checkpoints.
No downloaded or simulated model is silently substituted.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path

from tools.v211_four_engine_coordinator import run_candidates
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors
from tools.v211_real_engine_manifest import load_real_engine_manifest
from tools.v211_four_engine_safe_selection import select_conservative_candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(source: Path, output_dir: Path, config: Path, size: tuple[int, int], *, real_engines: bool = True, v2_reference: Path | None = None) -> dict:
    output_dir = Path(output_dir)
    if real_engines:
        commands = load_real_engine_manifest(config)
    else:
        raw = json.loads(config.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != set(ENGINES):
            raise ValueError("config must contain exactly the four engines")
        commands = {}
        for name in ENGINES:
            argv = raw[name]
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise ValueError("invalid argv for " + name)
            commands[name] = EngineCommand(tuple(argv))
    result = run_candidates(source, output_dir, size, make_processors(commands))
    report = {
        "research_only": True,
        "real_engine_manifest_preflight_passed": real_engines,
        "real_engine_inference_proven": False,  # Successful subprocess output alone cannot prove model inference.
        "completed_engine_count": len(result["candidates"]),
        "completed_engine_names": [item.engine for item in result["candidates"]],
        "fusion_implemented": False,
        "ready_for_fusion_research": result["ready_for_fusion_research"],
        "quality_certified": False,
        "source_sha256": _sha256(source),
        "candidate_sha256": {item.engine: _sha256(item.path) for item in result["candidates"]},
        "candidates": {item.engine: str(item.path) for item in result["candidates"]},
        "failures": result["failures"],
    }
    if v2_reference is not None:
        if result["ready_for_fusion_research"]:
            try:
                selection = select_conservative_candidate(
                    source, v2_reference,
                    {item.engine: item.path for item in result["candidates"]},
                    output_dir / "four_engine_selected.png",
                )
                report["conservative_selection"] = selection
            except (OSError, ValueError, RuntimeError) as exc:
                report["selection_error"] = type(exc).__name__ + ": " + str(exc)
                report["ready_for_fusion_research"] = False
                (output_dir / "four_engine_selected.png").unlink(missing_ok=True)
        else:
            report["selection_error"] = "All four valid engine outputs required"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "four_engine_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--research-commands", action="store_true",
                        help="Explicit research-only commands; default requires real engines")
    parser.add_argument("--v2-reference", type=Path,
                        help="Trusted V2 output at target dimensions")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    report = run(args.source, args.output_dir, args.config, (args.width, args.height),
                 real_engines=not args.research_commands, v2_reference=args.v2_reference)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ready_for_fusion_research"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
