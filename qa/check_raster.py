#!/usr/bin/env python3
"""V2 print QA: inspect paired raster files; NEVER certifies physical prints.

Usage: python qa/check_raster.py source.png output.tif --report qa-result.json
       python qa/check_raster.py source.png output.png --report result.json --expect-same-size
Dependencies: Pillow, numpy. No customer files are uploaded.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# Full decoding of huge vinyl rasters can exhaust CI memory. Above this bound,
# report the pixel decode as untested rather than claiming a successful decode.
MAX_FULL_DECODE_PIXELS = 16_000_000


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(source, output, expect_same_size=False):
    checks = {}
    details = {}
    with Image.open(source) as src, Image.open(output) as dst:
        details["source_mode"] = src.mode
        details["output_mode"] = dst.mode
        details["source_size"] = list(src.size)
        details["output_size"] = list(dst.size)
        details["output_dpi"] = [float(value) for value in (dst.info.get("dpi") or ())]
        if dst.width * dst.height <= MAX_FULL_DECODE_PIXELS:
            dst.load()
            checks["output_decodes"] = {
                "status": "PASS", "reason": "Pillow decoded every output pixel"}
        else:
            checks["output_decodes"] = {
                "status": "NOT_TESTED",
                "reason": "Output exceeds full-decode memory guard; header only, verify on target machine"}
        if expect_same_size:
            ok = src.size == dst.size
            checks["size_match"] = {"status": "PASS" if ok else "FAIL",
                                    "reason": f"{src.size} -> {dst.size}"}
        else:
            checks["size_match"] = {"status": "NOT_TESTED",
                                    "reason": "Upscaling/resize permitted; specify --expect-same-size to enforce"}
        source_alpha = "A" in src.getbands() or "transparency" in src.info
        if source_alpha:
            output_alpha = "A" in dst.getbands() or "transparency" in dst.info
            checks["alpha_channel"] = {"status": "PASS" if output_alpha else "FAIL",
                                        "reason": "source has transparency; output must retain it"}
            if output_alpha and max(src.width * src.height, dst.width * dst.height) > MAX_FULL_DECODE_PIXELS:
                checks["alpha_exact_same_size"] = {
                    "status": "NOT_TESTED", "reason": "Source or output exceeds safe alpha-decode budget; exact alpha untested"}
                checks["alpha_edge_visual"] = {
                    "status": "NOT_TESTED", "reason": "Requires Photoshop contrasting-background review"}
            elif output_alpha:
                a = np.asarray(dst.convert("RGBA").getchannel("A"))
                details["output_alpha_min"] = int(a.min())
                details["output_alpha_max"] = int(a.max())
                details["output_partial_alpha_pixels"] = int(np.count_nonzero((a > 0) & (a < 255)))
                sa = np.asarray(src.convert("RGBA").getchannel("A"))
                if src.size == dst.size:
                    equal = np.array_equal(sa, a)
                    checks["alpha_exact_same_size"] = {
                        "status": "PASS" if equal else "FAIL",
                        "reason": "Exact alpha equality only applies when dimensions match"}
                else:
                    checks["alpha_exact_same_size"] = {
                        "status": "NOT_TESTED", "reason": "Different dimensions; no exact alpha reference"}
                checks["alpha_edge_visual"] = {
                    "status": "NOT_TESTED",
                    "reason": "Requires Photoshop composite on black/white/saturated backgrounds"}
            else:
                checks["alpha_exact_same_size"] = {"status": "FAIL", "reason": "Output lacks alpha"}
                checks["alpha_edge_visual"] = {"status": "NOT_TESTED", "reason": "No alpha to inspect"}
        else:
            checks["alpha_channel"] = {"status": "NOT_APPLICABLE", "reason": "Source has no transparency"}
    for name in ("graphic_edges", "flat_color", "thai_text", "six_sliders_zero",
                 "face_identity", "preview_zoom", "tile_seams", "physical_print"):
        checks[name] = {"status": "NOT_TESTED", "reason": "Needs controlled fixture and/or human evidence"}
    return checks, details


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expect-same-size", action="store_true")
    args = parser.parse_args(argv)
    result = {"schema_version": 1, "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    try:
        result["source_sha256"] = digest(args.source)
        result["output_sha256"] = digest(args.output)
        checks, details = inspect(args.source, args.output, args.expect_same_size)
        result.update(checks=checks, details=details)
        statuses = [v["status"] for v in checks.values()]
        result["automated_checks"] = "FAIL" if "FAIL" in statuses else "PASS_WITH_UNTESTED"
    except Exception as exc:
        result["automated_checks"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["print_certification"] = "NOT_CERTIFIED"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['automated_checks']}: {args.report} (print certification: NOT_CERTIFIED)")
    return 1 if result["automated_checks"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
