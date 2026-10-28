#!/usr/bin/env python3
"""V2 print QA: inspect paired raster files; NEVER certifies physical prints.

Usage: python qa/check_raster.py source.png output.tif --report qa-result.json
       python qa/check_raster.py source.png output.png --report result.json --expect-same-size
Dependencies: Pillow, numpy. No customer files are uploaded.
"""
import argparse
import hashlib
import json
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

# Full decoding of huge vinyl rasters can exhaust CI memory. Above this bound,
# report the pixel decode as untested rather than claiming a successful decode.
MAX_FULL_DECODE_PIXELS = 16_000_000


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_icc(output):
    """Inspect only embedded metadata; never claim a printer/media match."""
    blob = output.info.get("icc_profile")
    if not blob:
        return None
    try:
        profile = ImageCms.ImageCmsProfile(BytesIO(blob))
        return {
            "name": ImageCms.getProfileDescription(profile).strip(),
            "color_space": str(profile.profile.xcolor_space).strip().upper(),
            "bytes": len(blob),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "bytes": len(blob)}


def inspect(source, output, expect_same_size=False):
    checks = {}
    details = {}
    with Image.open(source) as src, Image.open(output) as dst:
        details["source_mode"] = src.mode
        details["output_mode"] = dst.mode
        details["source_size"] = list(src.size)
        details["output_size"] = list(dst.size)
        details["output_dpi"] = [float(value) for value in (dst.info.get("dpi") or ())]
        embedded = inspect_icc(dst)
        if embedded is not None:
            details["output_icc"] = embedded
        if dst.mode == "CMYK":
            if embedded is None:
                checks["cmyk_icc_consistency"] = {
                    "status": "NOT_TESTED",
                    "reason": "CMYK has no embedded ICC; confirm how the RIP assigns its profile",
                }
            elif embedded.get("error"):
                checks["cmyk_icc_consistency"] = {
                    "status": "FAIL", "reason": "Embedded ICC cannot be parsed",
                }
            elif embedded["color_space"] != "CMYK":
                checks["cmyk_icc_consistency"] = {
                    "status": "FAIL",
                    "reason": "Embedded ICC colour space does not match CMYK raster",
                }
            else:
                checks["cmyk_icc_consistency"] = {
                    "status": "PASS", "reason": "Embedded ICC exists and has CMYK colour space",
                }
                name = embedded["name"].lower()
                if any(token in name for token in ("gracol", "swop", "fogra", "iso coated")):
                    details["icc_advisory"] = (
                        "This is a generic coated/offset press profile; it does not "
                        "establish calibration for a specific solvent printer, ink and vinyl"
                    )
        elif embedded is not None and embedded.get("error"):
            checks["embedded_icc_readable"] = {
                "status": "FAIL", "reason": "Raster contains an invalid embedded ICC",
            }
        checks["printer_ink_media_rip_match"] = {
            "status": "NOT_TESTED",
            "reason": "ICC embedding alone cannot prove printer, ink, media or RIP colour accuracy",
        }
        # A readable header is not proof that the original pixels are intact.
        # Decode bounded inputs too; otherwise a truncated source could pass.
        if src.width * src.height <= MAX_FULL_DECODE_PIXELS:
            src.load()
            checks["source_decodes"] = {
                "status": "PASS", "reason": "Pillow decoded every source pixel"}
        else:
            checks["source_decodes"] = {
                "status": "NOT_TESTED",
                "reason": "Source exceeds full-decode memory guard; header only, verify on target machine"}
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
        source_alpha = any(band.lower() == "a" for band in src.getbands()) or "transparency" in src.info
        # CMYK and JPEG outputs are intentionally opaque export paths.  Do
        # not incorrectly fail alpha retention when the operator selected an
        # opaque format; still require a white-matte Photoshop check.
        opaque_export = dst.mode == "CMYK" or dst.format in ("JPEG", "JPG")
        if source_alpha and opaque_export:
            details["source_alpha_export_policy"] = "flattened_for_opaque_format"
            for name in ("alpha_channel", "alpha_partial_preserved",
                         "alpha_nonopaque_preserved", "alpha_exact_same_size"):
                checks[name] = {
                    "status": "NOT_APPLICABLE",
                    "reason": "CMYK/JPEG export deliberately flattens input alpha",
                }
            checks["alpha_edge_visual"] = {
                "status": "NOT_TESTED",
                "reason": "Verify white matte and transparent-edge compositing before printing",
            }
        elif source_alpha:
            output_alpha = any(band.lower() == "a" for band in dst.getbands()) or "transparency" in dst.info
            checks["alpha_channel"] = {"status": "PASS" if output_alpha else "FAIL",
                                        "reason": "source has transparency; output must retain it"}
            if output_alpha and max(src.width * src.height, dst.width * dst.height) > MAX_FULL_DECODE_PIXELS:
                checks["alpha_partial_preserved"] = {
                    "status": "NOT_TESTED", "reason": "Source or output exceeds safe alpha-decode budget"}
                checks["alpha_nonopaque_preserved"] = {
                    "status": "NOT_TESTED", "reason": "Source or output exceeds safe alpha-decode budget"}
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
                # Preserve antialiased edge transparency, not just the A band.
                # If partial alpha existed in the input, an all-binary output
                # means translucent edges were destroyed even when some
                # completely transparent pixels survived.
                source_partial = bool(np.any((sa > 0) & (sa < 255)))
                output_partial = bool(np.any((a > 0) & (a < 255)))
                checks["alpha_partial_preserved"] = {
                    "status": "FAIL" if source_partial and not output_partial else "PASS",
                    "reason": "Source has partial alpha but output has only binary alpha"
                    if source_partial and not output_partial
                    else "Partial alpha retained or absent from source",
                }
                # An RGBA output can be entirely opaque despite retaining an A band.
                # Catch this even when a legitimate resize prevents pixelwise equality.
                lost_transparency = bool(np.any(sa < 255) and np.all(a == 255))
                checks["alpha_nonopaque_preserved"] = {
                    "status": "FAIL" if lost_transparency else "PASS",
                    "reason": "Source has nonopaque pixels but output is fully opaque"
                    if lost_transparency else "Output retains nonopaque pixels or source was opaque",
                }
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
                checks["alpha_partial_preserved"] = {"status": "FAIL", "reason": "Output lacks alpha"}
                checks["alpha_nonopaque_preserved"] = {"status": "FAIL", "reason": "Output lacks alpha"}
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
