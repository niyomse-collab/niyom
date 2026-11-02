"""Run actual four-engine subprocess inference; never substitute mocks.

Requires a separately provisioned, SHA256-pinned manifest and a real PNG input.
Outputs and report stay local or in a private CI artifact, not the repository.
A passing run proves execution, NOT visual improvement over approved V2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from tools.v211_four_engine_subprocess import ENGINES, make_processors
from tools.v211_real_engine_manifest import load_real_engine_manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(manifest: Path, source: Path, output_dir: Path) -> dict:
    # Validate ALL executable/model hashes before running ANY inference.
    processors = make_processors(load_real_engine_manifest(manifest))
    with Image.open(source) as img:
        img.verify()
    with Image.open(source) as img:
        if img.format != "PNG":
            raise ValueError("source must be PNG")
        source_size = img.size
        source_alpha = "A" in img.getbands()
        source_icc = img.info.get("icc_profile")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "real_inference_verified": False,
        "quality_improvement_verified": False,
        "source_sha256": sha256(source),
        "source_size": source_size,
        "engines": {},
    }
    report_path = output_dir / "real_inference_report.json"
    current_engine = None
    try:
        for engine in ENGINES:
            current_engine = engine
            destination = output_dir / (engine + ".png")
            destination.unlink(missing_ok=True)
            processors[engine](source, destination)
            with Image.open(destination) as image:
                image.load()
                if image.format != "PNG" or min(image.size) <= 0:
                    raise ValueError(engine + ": invalid PNG output")
                if source_alpha and "A" not in image.getbands():
                    raise ValueError(engine + ": alpha channel lost")
                if source_icc and image.info.get("icc_profile") != source_icc:
                    raise ValueError(engine + ": ICC changed or lost")
                report["engines"][engine] = {
                    "sha256": sha256(destination),
                    "size": list(image.size),
                    "mode": image.mode,
                    "alpha_preserved": not source_alpha or "A" in image.getbands(),
                    "icc_preserved": not source_icc or image.info.get("icc_profile") == source_icc,
                }
        report["real_inference_verified"] = True
        return report
    except Exception as exc:
        # Record the failing engine without claiming a successful four-engine run.
        # Do not embed subprocess stderr, paths or customer image content in artifacts.
        report["failed_engine"] = current_engine
        report["failure_type"] = type(exc).__name__
        raise
    finally:
        # Persist partial evidence on failure; the CLI still exits nonzero.
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.input, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
