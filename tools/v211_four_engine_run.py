"""Run all four configured AI engines on one image in the V2.1.1 research branch.

Usage:
 python -m tools.v211_four_engine_run input.png output_dir engines.json --width 1024 --height 1024

By default engines.json is a real-engine manifest with installed executables\nand model assets. With --research-commands it instead maps the four names to arrays of
executable arguments with {input} and {output} placeholders.
No checkpoint is downloaded or implicitly licensed by this tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.v211_four_engine_coordinator import run_candidates
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors
from tools.v211_real_engine_manifest import load_real_engine_manifest


def run(source: Path, output_dir: Path, config: Path, size: tuple[int, int], *, real_engines: bool = True) -> dict:
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
        "fusion_implemented": False,
        "ready_for_fusion_research": result["ready_for_fusion_research"],
        "quality_certified": False,
        "candidates": {item.engine: str(item.path) for item in result["candidates"]},
        "failures": result["failures"],
    }
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
    parser.add_argument("--research-commands", action="store_true", help="Explicitly allow generic research commands; default requires installed real AI engines")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    report = run(args.source, args.output_dir, args.config, (args.width, args.height), real_engines=not args.research_commands)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ready_for_fusion_research"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
