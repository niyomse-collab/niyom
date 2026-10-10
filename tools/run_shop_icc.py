"""Private local comparison of actual shop CMYK ICC workflow vs legacy exporter.

NEVER uploads the shop ICC or customer art to GitHub. This is explicitly
opt-in; a real CMYK output ICC file is required. No output ICC is fabricated.
Both paths receive the SAME RGB input pixels and exact profile bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_profile(icc: Path) -> str:
    from PIL import ImageCms
    if not icc.is_file():
        raise ValueError("Missing shop CMYK ICC/ICM profile. Provide the RIP/printer output ICC.")
    try:
        info = ImageCms.getOpenProfile(str(icc))
        space = str(info.profile.xcolor_space).strip().upper()
    except Exception as exc:
        raise ValueError(f"Cannot read shop ICC/ICM: {exc}") from exc
    if space != "CMYK":
        raise ValueError(f"Expected a CMYK output profile; found {space}")
    return space


def compare_real_icc(source: Path, icc: Path, destination: Path, dpi: int = 150) -> dict:
    import numpy as np
    from PIL import Image
    from signprint_ai.processing import save_image
    from independent_core.print_output import PrintSpec, export_print_image

    verify_profile(icc)
    if dpi <= 0:
        raise ValueError("Positive DPI required")
    if not source.is_file():
        raise FileNotFoundError(source)
    dest = destination.resolve()
    if dest == source.resolve() or dest == icc.resolve():
        raise ValueError("Do not overwrite sample art or the ICC file")

    dest.mkdir(parents=True, exist_ok=True)
    # Baseline intentionally uses the pre-existing app exporter, unchanged.
    # Convert exactly once to 8-bit RGB for both exporters.
    with Image.open(source) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8).copy()
    reference = dest / "reference-arm-cmyk.tif"
    candidate = dest / "candidate-niyomsil-cmyk.tif"
    save_image(rgb, reference, dpi=dpi, color_mode="CMYK",
               icc_profile_path=icc)
    export_print_image(rgb, candidate, PrintSpec(
        dpi=dpi, color_mode="CMYK", icc_profile=icc
    ))
    expected_profile = icc.read_bytes()
    with Image.open(reference) as left, Image.open(candidate) as right:
        source_ref = np.asarray(left).copy()
        source_new = np.asarray(right).copy()
        reference_icc = left.info.get("icc_profile")
        candidate_icc = right.info.get("icc_profile")
        dimensions = (left.size == right.size == (rgb.shape[1], rgb.shape[0]))
        modes = (left.mode, right.mode)
        dpi_reference = left.info.get("dpi")
        dpi_candidate = right.info.get("dpi")

    delta = np.abs(source_ref.astype(np.int16)-source_new.astype(np.int16))
    icc_matches = (
        reference_icc == expected_profile and
        candidate_icc == expected_profile
    )
    pixels_match = bool(np.array_equal(source_ref, source_new))
    passed = bool(
        dimensions and modes == ("CMYK", "CMYK") and
        icc_matches and pixels_match and
        dpi_reference is not None and dpi_candidate is not None and
        abs(dpi_reference[0]-dpi) < 1.1 and abs(dpi_candidate[0]-dpi) < 1.1
    )
    report = {
        "passed": passed,
        "icc_color_space": "CMYK",
        "icc_sha256": digest(icc),
        "source_sha256": digest(source),
        "source_dimensions": [rgb.shape[1], rgb.shape[0]],
        "dpi_expected": dpi,
        "mode_reference": modes[0],
        "mode_candidate": modes[1],
        "dimensions_match": dimensions,
        "icc_embedded_exact_match": icc_matches,
        "pixels_identical": pixels_match,
        "changed_pixel_count": int(np.count_nonzero(np.any(delta != 0, axis=2))),
        "max_cmyk_channel_difference": int(delta.max()),
        "reference_dpi": dpi_reference,
        "candidate_dpi": dpi_candidate,
        "limitations": (
            "Identical exported CMYK TIFFs do not establish printer calibration. "
            "RIP soft-proof, physical print, PDF/X OutputIntent and ink limits still require shop verification."
        )
    }
    (dest / "icc_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Local CMYK proof using the shop's real output ICC")
    parser.add_argument("--source", required=True, type=Path, help="Approved shop art file")
    parser.add_argument("--icc", required=True, type=Path, help="Actual CMYK printer/RIP output ICC")
    parser.add_argument("--out", type=Path, default=ROOT/"local-qa-results"/"icc")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    try:
        report = compare_real_icc(args.source, args.icc, args.out, dpi=args.dpi)
    except (ValueError, FileNotFoundError) as exc:
        print(f"CMYK test NOT passed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
