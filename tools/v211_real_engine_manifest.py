"""Preflight installed real engine executables and checkpoint assets.

No simulated inference or implicit downloads. The manifest supplies explicit
absolute paths to the four installed engines and their model assets.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from tools.v211_four_engine_subprocess import ENGINES, EngineCommand


def _verify_hash(path: Path, expected: str, engine: str) -> None:
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
        raise ValueError(engine + ": expected_sha256 must be a 64-character hex digest")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.lower():
        raise ValueError(engine + ": SHA256 mismatch for " + str(path))


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
        provenance = item.get("provenance")
        if not isinstance(provenance, dict) or not all(
            isinstance(provenance.get(key), str) and provenance[key].strip()
            for key in ("source_url", "license_name", "license_url")
        ):
            raise ValueError(engine + ": source_url, license_name and license_url provenance required")
        additional_notices = provenance.get("additional_license_notices", [])
        if not isinstance(additional_notices, list) or any(
            not isinstance(notice, dict)
            or not isinstance(notice.get("name"), str) or not notice["name"].strip()
            or not isinstance(notice.get("url"), str) or not notice["url"].strip()
            for notice in additional_notices
        ):
            raise ValueError(engine + ": additional license notices must include name and URL")
        _verify_hash(executable, item.get("executable_sha256"), engine)
        # Anime4KCPP v3.2.0 implements its algorithms in the shipped CLI.
        # Its official Windows archive has no separate .bin/.param model
        # weights; verification is anchored to the executable SHA-256 instead.
        # Never silently grant this exemption to a different engine.
        embedded_algorithm = item.get("embedded_algorithm") is True
        if embedded_algorithm and engine != "anime4k":
            raise ValueError(engine + ": embedded algorithm exemption forbidden")
        assets = item.get("model_assets", [])
        if not isinstance(assets, list) or not all(
            isinstance(a, dict) and isinstance(a.get("path"), str) for a in assets
        ):
            raise ValueError(engine + ": model assets must be individual files with SHA256")
        if (not assets and not embedded_algorithm) or (assets and embedded_algorithm):
            raise ValueError(engine + ": verified model assets required unless Anime4KCPP is embedded")
        for asset in assets:
            model = Path(asset['path'] if isinstance(asset, dict) else asset)
            if not model.is_absolute() or not model.exists():
                raise FileNotFoundError(engine + ": missing model asset: " + str(model))
            if model.is_file():
                valid = model.stat().st_size > 0
            elif model.is_dir():
                # NCNN Vulkan engines commonly distribute model files in a directory.
                valid = any(p.is_file() and p.stat().st_size > 0 for p in model.rglob("*"))
            else:
                valid = False
            if not valid:
                raise FileNotFoundError(engine + ": empty model asset: " + str(model))
            if not isinstance(asset, dict) or not model.is_file():
                raise ValueError(engine + ": model assets must be individual files with SHA256")
            _verify_hash(model, asset.get("sha256"), engine)
        args = item.get("args")
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(engine + ": args must be a string array")
        if not any("{input}" in a for a in args) or not any("{output}" in a for a in args):
            raise ValueError(engine + ": args must include input/output placeholders")
        commands[engine] = EngineCommand(
            (str(executable), *args), timeout_seconds=int(item.get("timeout_seconds", 1800))
        )
    return commands
