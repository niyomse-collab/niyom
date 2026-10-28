#!/usr/bin/env python3
"""Bounded, diagnostic CMYK white-matte probe for large V2/V2.1 print outputs.

Use: python qa/probe_cmyk_matte.py source.png output.tif --report result.json

Output code: 0 PASS; 1 FAIL; 2 NOT_TESTED. A PASS is not print certification.
For large source PNG or output TIFF, install pyvips on the checking machine.
If pyvips is unavailable, report NOT_TESTED instead of decoding a huge image.
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


def _open_explicit_print_header(path):
    # Pillow's global bomb guard is for unsolicited image decoding. This
    # checker opens only explicitly chosen files, and never fully decodes a
    # raster exceeding the bounded limits below. Restore the guard at once.
    original_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        return Image.open(path)
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit


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
        with _open_explicit_print_header(source_path) as source, \
             _open_explicit_print_header(output_path) as output:
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
            if abs(source.width / source.height - output.width / output.height) > 0.01:
                report["reason"] = "Source/output aspect ratios differ; cannot map probes safely"
                return report

            # Decode small alpha planes in memory. For real print-sized PNGs,
            # inspect only 5x5 regions with libvips; never materialize the
            # entire 100+ megapixel source in Python or Pillow.
            if source.width * source.height <= MAX_FULL_SOURCE_PIXELS:
                source_alpha = np.asarray(source.convert("RGBA").getchannel("A"))
                def is_zero_alpha(sx, sy):
                    return source_alpha[max(0, sy-2):sy+3,
                                        max(0, sx-2):sx+3].max() == 0
            else:
                try:
                    import pyvips
                except (ImportError, OSError):
                    report["reason"] = ("Source is large and pyvips is unavailable; "
                                        "full alpha decoding is intentionally not attempted")
                    return report
                options = {"access": "random", "fail_on": "error"}
                if Path(source_path).suffix.lower() in (".png", ".tif", ".tiff"):
                    options["unlimited"] = True
                vip_source = pyvips.Image.new_from_file(str(source_path), **options)
                if not vip_source.hasalpha():
                    report["reason"] = "Source alpha was not preserved by large-image decoder"
                    return report
                vip_alpha = vip_source.extract_band(vip_source.bands - 1)
                def is_zero_alpha(sx, sy):
                    left, top = max(0, sx-2), max(0, sy-2)
                    width = min(source.width, sx+3) - left
                    height = min(source.height, sy+3) - top
                    patch = vip_alpha.crop(left, top, width, height)
                    return not any(patch.cast("uchar").write_to_memory())

            positions = []
            for y in FRACTIONS:
                for x in FRACTIONS:
                    sx = _coordinate(x, source.width)
                    sy = _coordinate(y, source.height)
                    if not is_zero_alpha(sx, sy):
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
