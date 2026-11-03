"""Provision four pre-approved local AI engines without downloading or bundling binaries.

Lock JSON has exactly four engine keys. Each engine declares executable:
{"source": "/absolute/path", "sha256": "64 hex"}, model_assets: same
list, args with {input}/{output}, and provenance with source_url,
license_name, license_url. Destination must be a new empty directory.
No claim of real inference is made by provisioning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_real_engine_manifest import load_real_engine_manifest


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def provision(lock_path: Path, destination: Path) -> Path:
    # Reject symlink destinations rather than silently following them.
    if destination.is_symlink():
        raise ValueError("destination symlink is forbidden")
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("destination must not already exist")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or set(lock) != set(ENGINES):
        raise ValueError("lock must define exactly four engines")
    # Validate every source BEFORE copying anything. Never download or execute.
    validated = {}
    for engine in ENGINES:
        item = lock[engine]
        if not isinstance(item, dict):
            raise ValueError(engine + ": invalid configuration")
        provenance = item.get("provenance")
        if not isinstance(provenance, dict) or not all(
            isinstance(provenance.get(k), str) and provenance[k].strip()
            for k in ("source_url", "license_name", "license_url")
        ):
            raise ValueError(engine + ": missing source and license provenance")
        args = item.get("args")
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(engine + ": invalid arguments")
        if not any("{input}" in a for a in args) or not any("{output}" in a for a in args):
            raise ValueError(engine + ": input/output placeholders required")
        timeout = item.get("timeout_seconds", 1800)
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ValueError(engine + ": timeout_seconds must be an integer from 1 to 3600")
        assets = item.get("model_assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(engine + ": model files required")
        sources = [item.get("executable"), *assets]
        checked = []
        for spec in sources:
            if not isinstance(spec, dict):
                raise ValueError(engine + ": file and hash required")
            src = Path(spec.get("source", ""))
            expected = spec.get("sha256")
            if src.is_symlink():
                raise ValueError(engine + ": symlink source is forbidden")
            if not src.is_absolute() or not src.is_file() or src.stat().st_size == 0:
                raise FileNotFoundError(engine + ": missing nonempty local file")
            if not isinstance(expected, str) or len(expected) != 64 or any(
                c not in "0123456789abcdefABCDEF" for c in expected
            ):
                raise ValueError(engine + ": SHA256 required")
            if digest(src) != expected.lower():
                raise ValueError(engine + ": SHA256 mismatch")
            checked.append((src, expected.lower()))
        validated[engine] = (item, checked)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {}
    try:
        for engine, (item, checked) in validated.items():
            folder = destination / engine
            folder.mkdir()
            output_paths = []
            for index, (src, expected) in enumerate(checked):
                # Unique indexed names avoid collisions and path traversal.
                target = folder / (str(index) + "_" + src.name)
                shutil.copyfile(src, target)
                if digest(target) != expected:
                    raise ValueError(engine + ": copied file SHA256 mismatch")
                output_paths.append(target)
            manifest[engine] = {
                "executable": str(output_paths[0]),
                "executable_sha256": checked[0][1],
                "model_assets": [
                    {"path": str(p), "sha256": checked[i][1]}
                    for i, p in enumerate(output_paths[1:], 1)
                ],
                "args": item["args"],
                "provenance": item["provenance"],
                "timeout_seconds": item.get("timeout_seconds", 1800),
            }
        path = destination / "engines.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        load_real_engine_manifest(path)
        return path
    except Exception:
        # Never leave a partly provisioned directory that looks usable.
        shutil.rmtree(destination)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(provision(args.lock, args.destination))


if __name__ == "__main__":
    main()
