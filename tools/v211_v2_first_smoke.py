"""Real V2 baseline smoke test: requires the existing NCNN executable and weights.

Run: python -m tools.v211_v2_first_smoke input.png output.png --scale 2
This never substitutes a resize for unavailable Real-ESRGAN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from signprint_ai.pipeline import PrintEnhancementPipeline
from signprint_ai.processing import EnhanceSettings


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--scale", type=int, choices=(2, 4), default=2)
    args = p.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if source == output:
        p.error("Source and output must differ")
    pipeline = PrintEnhancementPipeline()
    if not pipeline.ai.available:
        raise SystemExit("FAIL: V2 Real-ESRGAN NCNN binary/models unavailable; no fake upscale")
    with Image.open(source) as image:
        w, h = image.size
        has_alpha = "A" in image.getbands()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = EnhanceSettings(ai_scale=args.scale, v1_baseline=True)
    result = pipeline.process(source, output, settings, use_ai=True)
    with Image.open(output) as image:
        actual = image.size
        output_alpha = "A" in image.getbands()
        image.verify()
    expected = (w * args.scale, h * args.scale)
    if actual != expected:
        raise SystemExit(f"FAIL: output dimensions {actual}, expected {expected}")
    if has_alpha and not output_alpha:
        raise SystemExit("FAIL: transparent input lost alpha")
    report = {
        "engine": "Real-ESRGAN NCNN",
        "baseline": "v2-ncnn-stable",
        "source_sha256": digest(source),
        "output_sha256": digest(output),
        "expected_size": expected,
        "actual_size": actual,
        "alpha_preserved": not has_alpha or output_alpha,
        "pipeline_result": result,
        "inference_quality_certified": False,
        "note": "Output validated; visual A/B versus accepted V2 still required",
    }
    report_path = output.with_suffix(".smoke.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
