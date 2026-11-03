"""Inspect real four-engine installations before attempting inference.

Usage: python -m tools.v211_four_engine_preflight engines.json
Returns exit code 0 only when the manifest validates. No models are executed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_real_engine_manifest import load_real_engine_manifest


def audit(manifest: Path) -> dict:
    try:
        commands = load_real_engine_manifest(manifest)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {
            "ready": False,
            "real_inference_verified": False,
            "error": type(exc).__name__ + ": " + str(exc),
        }
    return {
        "ready": set(commands) == set(ENGINES),
        "engines": list(ENGINES),
        "real_inference_verified": False,
        "note": "Executable and model paths checked; actual inference not run.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not result["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
