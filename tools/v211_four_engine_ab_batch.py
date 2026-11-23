"""Private 12-category V2 versus V2.1.1 A/B review suite.

This tool reads only local user-supplied files. It never uploads artwork and
never treats a completed report as visual-quality or print-quality approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tools import v211_four_engine_ab_report as ab_report

REQUIRED_CATEGORIES = tuple(ab_report.REVIEW_REGION_LABELS)
CASE_FIELDS = {"label", "source", "v2_reference", "candidate", "evidence", "crop"}
COLUMNS = 3
CELL_WIDTH = 640
CELL_HEIGHT = 390


class BatchManifestError(ValueError):
    """A local 12-category manifest does not satisfy the exact input contract."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _resolve_input(value: object, base_dir: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise BatchManifestError("case_input_path_invalid")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _load_cases(manifest_path: Path) -> dict[str, dict]:
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not manifest_path.is_file():
        raise BatchManifestError("manifest_missing")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise BatchManifestError("manifest_unreadable")
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "cases"}
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
    ):
        raise BatchManifestError("manifest_schema_invalid")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != len(REQUIRED_CATEGORIES):
        raise BatchManifestError("category_count_mismatch")

    cases: dict[str, dict] = {}
    for raw in raw_cases:
        if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
            raise BatchManifestError("case_fields_invalid")
        label = raw.get("label")
        if not isinstance(label, str) or label not in REQUIRED_CATEGORIES:
            raise BatchManifestError("category_label_unknown")
        if label in cases:
            raise BatchManifestError("duplicate_category_label")
        crop = raw.get("crop")
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or any(type(value) is not int for value in crop)
        ):
            raise BatchManifestError("category_crop_invalid")
        try:
            crop_box = ab_report.parse_crop(",".join(str(value) for value in crop))
        except argparse.ArgumentTypeError:
            raise BatchManifestError("category_crop_invalid")

        paths = {
            key: _resolve_input(raw.get(key), manifest_path.parent)
            for key in ("source", "v2_reference", "candidate", "evidence")
        }
        if not all(path.is_file() for path in paths.values()):
            raise BatchManifestError("case_input_missing")
        cases[label] = {"label": label, **paths, "crop": crop_box}

    if set(cases) != set(REQUIRED_CATEGORIES):
        raise BatchManifestError("category_coverage_incomplete")
    return cases


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _create_category_contact_sheet(output_dir: Path, categories: list[dict]) -> str:
    """Create a compact contact sheet from the 12 already-generated review crops."""
    rows = (len(REQUIRED_CATEGORIES) + COLUMNS - 1) // COLUMNS
    sheet = Image.new(
        "RGB",
        (COLUMNS * CELL_WIDTH, rows * CELL_HEIGHT),
        (30, 30, 30),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    try:
        for index, category in enumerate(categories):
            row, column = divmod(index, COLUMNS)
            left = column * CELL_WIDTH
            top = row * CELL_HEIGHT
            draw.rectangle(
                (left, top, left + CELL_WIDTH - 1, top + 31),
                fill=(52, 52, 52),
            )
            draw.text(
                (left + 12, top + 9),
                category["label"].upper(),
                fill=(255, 255, 255),
                font=font,
            )
            crop_path = output_dir / category["crop_preview"]
            with Image.open(crop_path) as opened:
                preview = opened.convert("RGB")
                preview.thumbnail(
                    (CELL_WIDTH - 24, CELL_HEIGHT - 48),
                    Image.Resampling.LANCZOS,
                )
                x = left + (CELL_WIDTH - preview.width) // 2
                y = top + 36 + (CELL_HEIGHT - 40 - preview.height) // 2
                sheet.paste(preview, (x, y))
                preview.close()
        name = "ab_12_category_contact_sheet.png"
        sheet.save(output_dir / name, format="PNG")
        return name
    finally:
        sheet.close()


def run(manifest, output_dir) -> dict:
    """Run one private A/B report for each of the 12 required artwork categories."""
    output = ab_report._ensure_private_output_dir(Path(output_dir))
    report = {
        "schema_version": 1,
        "status": "blocked",
        "block_reasons": [],
        "required_categories": list(REQUIRED_CATEGORIES),
        "category_count": len(REQUIRED_CATEGORIES),
        "categories": [],
        "all_12_categories_ready_for_human_review": False,
        "input_files_unchanged": False,
        "evidence_authenticity_verified": False,
        "evidence_verification_scope": (
            "per-category unsigned sidecar hash bindings are checked; sidecar claims "
            "are not cryptographically authenticated"
        ),
        "quality_certified": False,
        "visual_quality_certified": False,
        "print_quality_certified": False,
        "human_review_required": True,
        "artifacts": [],
        "privacy": {
            "input_paths_included": False,
            "commands_included": False,
            "logs_included": False,
            "image_pixels_embedded_in_json": False,
        },
    }

    manifest_path = Path(manifest).expanduser().resolve()
    try:
        cases = _load_cases(manifest_path)
    except BatchManifestError as exc:
        report["block_reasons"].append("manifest_" + exc.code)
        _write_json(output / "ab_12_category_report.json", report)
        return report

    report["manifest_sha256"] = ab_report.sha256_file(manifest_path)
    category_results = []
    for label in REQUIRED_CATEGORIES:
        case = cases[label]
        case_dir = output / label
        crop_name = f"ab_crop_01_{label}.png"
        try:
            single = ab_report.run(
                case["source"],
                case["v2_reference"],
                case["candidate"],
                case["evidence"],
                case_dir,
                crops=(case["crop"],),
                crop_labels=(label,),
                max_preview_edge=512,
            )
            crop_path = case_dir / crop_name
            ready = (
                single.get("status") == "ready_for_human_review"
                and crop_path.is_file()
                and single.get("input_files_unchanged") is True
            )
            region_metrics = None
            regions = single.get("review_regions")
            if isinstance(regions, list) and regions:
                region_metrics = regions[0].get("metrics")
            entry = {
                "label": label,
                "status": "ready_for_human_review" if ready else "blocked",
                "block_reasons": list(single.get("block_reasons") or []),
                "report": f"{label}/ab_report.json",
                "crop_preview": f"{label}/{crop_name}" if crop_path.is_file() else None,
                "input_files_unchanged": single.get("input_files_unchanged") is True,
                "metrics": single.get("metrics"),
                "region_metrics": region_metrics,
            }
        except Exception as exc:
            entry = {
                "label": label,
                "status": "blocked",
                "block_reasons": ["category_processing_" + type(exc).__name__.lower()],
                "report": f"{label}/ab_report.json",
                "crop_preview": None,
                "input_files_unchanged": False,
                "metrics": None,
                "region_metrics": None,
            }
        category_results.append(entry)

    all_ready = (
        len(category_results) == len(REQUIRED_CATEGORIES)
        and all(item["status"] == "ready_for_human_review" for item in category_results)
    )
    report["categories"] = category_results
    report["category_labels"] = [item["label"] for item in category_results]
    report["review_region_labels_are_user_supplied"] = True
    report["review_region_coverage"] = {
        label: any(item["label"] == label for item in category_results)
        for label in REQUIRED_CATEGORIES
    }
    report["review_region_coverage_count"] = sum(report["review_region_coverage"].values())
    report["all_review_regions_covered"] = (
        report["review_region_coverage_count"] == len(REQUIRED_CATEGORIES)
    )
    report["input_files_unchanged"] = all(
        item["input_files_unchanged"] for item in category_results
    )
    report["all_12_categories_ready_for_human_review"] = all_ready
    report["artifacts"] = [
        item["report"] for item in category_results
    ] + [
        item["crop_preview"] for item in category_results if item["crop_preview"]
    ]

    if all_ready:
        try:
            contact_sheet = _create_category_contact_sheet(output, category_results)
            report["artifacts"].append(contact_sheet)
            report["status"] = "ready_for_human_review"
        except Exception as exc:
            report["block_reasons"].append(
                "category_contact_sheet_" + type(exc).__name__.lower()
            )
    else:
        report["block_reasons"].append("one_or_more_categories_not_ready")
    _write_json(output / "ab_12_category_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a private 12-category V2 versus V2.1.1 A/B review pack."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.manifest, args.output_dir)
    except ab_report.ABReportError as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        raise SystemExit(2)
    print(json.dumps({
        "status": report["status"],
        "category_count": report["category_count"],
        "review_region_coverage_count": report.get("review_region_coverage_count", 0),
        "all_12_categories_ready_for_human_review": report[
            "all_12_categories_ready_for_human_review"
        ],
        "quality_certified": False,
    }, ensure_ascii=False))
    if report["status"] != "ready_for_human_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
