"""Preflight installed real engine executables and checkpoint assets.

No simulated inference or implicit downloads. The manifest supplies explicit
absolute paths to the four installed engines and their model assets.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from tools.v211_four_engine_subprocess import ENGINES, EngineCommand


def load_real_engine_manifest(path: Path) -> dict[str, EngineCommand]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != set(ENGINES):
        raise ValueError("manifest must configure exactly four engines")
    commands = {}
    for engine in ENGINES:
        item = data[engine]
        if not isinstance(item, dict):
            raise ValueError(engine + ": expected engine configuration")
        executable = Path(item["executable"])
        if not executable.is_absolute() or not executable.is_file():
            raise FileNotFoundError(engine + ": executable not installed: " + str(executable))
        assets = item.get("model_assets", [])
        if not isinstance(assets, list) or not assets:
            raise ValueError(engine + ": real model assets must be declared")
        for asset in assets:
            model = Path(asset)
            if not model.is_absolute() or not model.is_file() or model.stat().st_size == 0:
                raise FileNotFoundError(engine + ": missing model asset: " + str(model))
        args = item.get("args")
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(engine + ": args must be a string array")
        commands[engine] = EngineCommand(
            (str(executable), *args), timeout_seconds=int(item.get("timeout_seconds", 1800))
        )
    return commands
