#!/usr/bin/env python3
"""Bounded, diagnostic CMYK white-matte probe for large V2/V2.1 print outputs.

Use: python qa/probe_cmyk_matte.py source.png output.tif --report result.json

Output code: 0 PASS; 1 FAIL; 2 NOT_TESTED. A PASS is not print certification.
For large TIFF output, install pyvips on the checking machine. If pyvips is
unavailable, report NOT_TESTED instead of decoding a multi-gigabyte image.
Only probes source pixels whose 5x5 neighbourhood is entirely alpha=0.
"""
from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

MAX_FULL_SOURCE_PIXELS = 16_000_000
MAX_FULL_OUTPUT_PIXELS = 16_000_000
FRACTIONS = (0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0)


def _coordinate(value, limit):
    return max(0, min(limit - 1, round(value * (limit - 1))))


def inspect(source_path, output_path):
    report = {
        "schema_version": 1,
        "automated_check": "NOT_TESTED",
        "print_certification": "NOT_CERTIFIED",
        "source": str(source_path),
        "output": str(output_path),
        "samples": [],
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(source_path) as source, Image.open(output_path) as output:
            report["source_size"] = list(source.size)
            report["output_size"] = list(output.size)
            report["source_mode"] = source.mode
            report["output_mode"] = output.mode
            if output.mode != "CMYK":
                report["automated_check"] = "FAIL"
                report["reason"] = "Expected a CMYK TIFF/JPEG raster"
                return report
            if "A" not in source.getbands() and "transparency" not in source.info:
                report["reason"] = "Source has no alpha to verify white matte"
                return report
            if source.width * source.height > MAX_FULL_SOURCE_PIXELS:
                report["reason"] = "Source exceeds bounded alpha-decode budget"
                return report
            if abs(source.width / source.height - output.width / output.height) > 0.01:
                report["reason"] = "Source/output aspect ratios differ; cannot map probes safely"
                return report

            source_alpha = np.asarray(source.convert("RGBA").getchannel("A"))
            positions = []
            for y in FRACTIONS:
                for x in FRACTIONS:
                    sx = _coordinate(x, source.width)
                    sy = _coordinate(y, source.height)
                    if source_alpha[max(0, sy-2):sy+3, max(0, sx-2):sx+3].max() != 0:
                        continue
                    positions.append((x, y,
                                      _coordinate(x, output.width),
                                      _coordinate(y, output.height)))
            if len(positions) < 3:
                report["reason"] = "Fewer than three clear zero-alpha probe regions"
                return report
            if output.width * output.height <= MAX_FULL_OUTPUT_PIXELS:
                output.load()
                def read_pixel(x, y):
                    return tuple(output.getpixel((x, y)))
            else:
                try:
                    import pyvips
                except (ImportError, OSError):
                    report["reason"] = ("Output is large and pyvips is unavailable; "
                                        "full decoding is intentionally not attempted")
                    return report
                vip = pyvips.Image.new_from_file(str(output_path),
                                                 access="random", fail_on="error")
                if vip.bands != 4 or vip.interpretation != "cmyk":
                    report["automated_check"] = "FAIL"
                    report["reason"] = "Large output was not decoded as four-band CMYK"
                    return report
                def read_pixel(x, y):
                    return tuple(vip.crop(x, y, 1, 1).cast("uchar").write_to_memory()[:4])
            failures = 0
            for fx, fy, dx, dy in positions:
                cmyk = read_pixel(dx, dy)
                total = int(sum(cmyk))
                # Deliberately tolerant of small ICC white-paper offsets.
                bad = total > 80 or int(cmyk[3]) > 40
                failures += int(bad)
                report["samples"].append({
                    "normalized_position": [fx, fy],
                    "output_cmyk": list(cmyk),
                    "total_ink": total,
                    "status": "FAIL" if bad else "PASS",
                })
            report["sample_count"] = len(positions)
            report["bad_sample_count"] = failures
            report["automated_check"] = "FAIL" if failures else "PASS"
            report["reason"] = (
                "CMYK ink detected in source-zero-alpha regions"
                if failures else "Probed zero-alpha regions have a white CMYK matte"
            )
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.source, args.output)
    except Exception as exc:
        result = {
            "automated_check": "FAIL", "print_certification": "NOT_CERTIFIED",
            "reason": f"{type(exc).__name__}: {exc}", "samples": [],
        }
    result["checked_utc"] = datetime.now(timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"{result['automated_check']}: {result['reason']}")
    return {"PASS": 0, "FAIL": 1, "NOT_TESTED": 2}[result["automated_check"]]


if __name__ == "__main__":
    raise SystemExit(main())
