"""CI integration proof using generic Ghostscript CMYK test profile only.

The generic profile is installed from the OS package. Never treat it as the
print shop's media/ink/RIP profile. The reference and independent exporters
must create TIFF with identical CMYK pixels and embedded ICC bytes.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from tools.run_shop_icc import compare_real_icc, verify_profile


def create_fixture(path: Path) -> None:
    image = Image.new("RGB", (192, 112), "white")
    for x in range(image.width):
        for y in range(image.height):
            image.putpixel((x, y), (
                min(255, round(x * 255 / (image.width - 1))),
                round((image.height - 1 - y) * 255 / (image.height - 1)),
                round(((x + y) % 75) / 74 * 255)
            ))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 40, 40), fill=(255, 0, 0))
    draw.rectangle((44, 8, 76, 40), fill=(0, 255, 0))
    draw.rectangle((80, 8, 112, 40), fill=(0, 0, 255))
    draw.rectangle((116, 8, 148, 40), fill=(0, 0, 0))
    draw.rectangle((152, 8, 184, 40), fill=(255, 255, 255))
    image.save(path, "PNG")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic non-shop ICC conversion integration")
    parser.add_argument("--icc", type=Path, required=True, help="OS-supplied CMYK profile; never the shop's private ICC")
    parser.add_argument("--out", type=Path, default=Path("generic-cmyk-test-evidence"))
    args = parser.parse_args()
    verify_profile(args.icc)
    args.out.mkdir(parents=True, exist_ok=True)
    fixture = args.out / "synthetic-rgb-source.png"
    create_fixture(fixture)

    tests = {}
    for dpi in (150, 300):
        results = compare_real_icc(
            fixture, args.icc, args.out / f"output_{dpi}dpi", dpi=dpi
        )
        if not results["passed"]:
            raise AssertionError(f"CMYK comparison failed at {dpi} DPI: {results}")
        tests[str(dpi)] = results

    report = {
        "passed": True,
        "profile_origin": "generic Ghostscript libgs-common default_cmyk.icc",
        "NOT_SHOP_PROFILE": True,
        "tests": tests,
        "warning": (
            "RGB->CMYK TIFF conversion and parity verified against unchanged ARM exporter. "
            "This does NOT verify the user's vinyl printer, ink, RIP, rendering intent, "
            "colorimetric accuracy, or physical print output."
        ),
    }
    (args.out / "generic-cmyk-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "passed": True,
        "dpi_cases": list(tests),
        "reference_parity": {k: tests[k]["pixels_identical"] for k in tests},
        "ICC_profile_embedded": {k: tests[k]["icc_embedded_exact_match"] for k in tests},
        "NOT_SHOP_PROFILE": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
