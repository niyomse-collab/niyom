import json
from pathlib import Path

from PIL import Image

from tools import v211_four_engine_ab_batch as batch
from tools.v211_four_engine_ab_report import REVIEW_REGION_LABELS
from tests.test_v211_four_engine_ab_report import _fixture


def _batch_manifest(tmp_path, *, omit=None):
    cases = []
    inputs = tmp_path / "inputs"
    for label in REVIEW_REGION_LABELS:
        if label == omit:
            continue
        folder = inputs / label
        folder.mkdir(parents=True, exist_ok=True)
        source, v2, candidate, evidence = _fixture(folder)
        cases.append({
            "label": label,
            "source": str(source.relative_to(tmp_path)),
            "v2_reference": str(v2.relative_to(tmp_path)),
            "candidate": str(candidate.relative_to(tmp_path)),
            "evidence": str(evidence.relative_to(tmp_path)),
            "crop": [8, 6, 16, 12],
        })
    manifest = tmp_path / "ab-12-categories.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "cases": cases,
    }), encoding="utf-8")
    return manifest, cases


def test_batch_ab_requires_all_12_categories_and_creates_private_review_pack(tmp_path):
    manifest, cases = _batch_manifest(tmp_path)
    hashes_before = {
        path: batch.ab_report.sha256_file(tmp_path / path)
        for case in cases
        for path in (case["source"], case["v2_reference"], case["candidate"], case["evidence"])
    }
    output = tmp_path / "ab-12-output"

    report = batch.run(manifest, output)

    assert report["status"] == "ready_for_human_review"
    assert report["category_count"] == 12
    assert report["category_labels"] == list(REVIEW_REGION_LABELS)
    assert report["review_region_coverage_count"] == 12
    assert report["all_review_regions_covered"] is True
    assert report["all_12_categories_ready_for_human_review"] is True
    assert report["quality_certified"] is False
    assert report["visual_quality_certified"] is False
    assert report["print_quality_certified"] is False
    assert report["evidence_authenticity_verified"] is False
    assert (output / "ab_12_category_contact_sheet.png").is_file()
    assert (output / "ab_12_category_report.json").is_file()
    for label in REVIEW_REGION_LABELS:
        assert (output / label / f"ab_crop_01_{label}.png").is_file()
    persisted = (output / "ab_12_category_report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in persisted
    assert all(batch.ab_report.sha256_file(path) == digest for path, digest in hashes_before.items())


def test_batch_ab_blocks_missing_category_before_processing_images(tmp_path):
    manifest, _ = _batch_manifest(tmp_path, omit=REVIEW_REGION_LABELS[-1])
    output = tmp_path / "ab-12-missing"
    report = batch.run(manifest, output)

    assert report["status"] == "blocked"
    assert report["block_reasons"] == ["manifest_category_count_mismatch"]
    assert not (output / "ab_12_category_contact_sheet.png").exists()
    assert not any((output / label).exists() for label in REVIEW_REGION_LABELS)


def test_batch_ab_blocks_duplicate_category_label(tmp_path):
    manifest, cases = _batch_manifest(tmp_path)
    cases[-1]["label"] = cases[0]["label"]
    manifest.write_text(json.dumps({"schema_version": 1, "cases": cases}), encoding="utf-8")
    output = tmp_path / "ab-12-duplicate"
    report = batch.run(manifest, output)

    assert report["status"] == "blocked"
    assert report["block_reasons"] == ["manifest_duplicate_category_label"]
    assert not (output / "ab_12_category_contact_sheet.png").exists()


def test_batch_ab_blocks_one_invalid_engine_evidence_and_withholds_contact_sheet(tmp_path):
    manifest, cases = _batch_manifest(tmp_path)
    selected = next(item for item in cases if item["label"] == "thai_pattern")
    evidence_path = tmp_path / selected["evidence"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["qa_image_sha256"] = "0" * 64
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    output = tmp_path / "ab-12-invalid-evidence"

    report = batch.run(manifest, output)

    assert report["status"] == "blocked"
    assert report["all_12_categories_ready_for_human_review"] is False
    blocked = next(item for item in report["categories"] if item["label"] == "thai_pattern")
    assert blocked["status"] == "blocked"
    assert "qa_image_sha256_mismatch" in blocked["block_reasons"]
    assert not (output / "ab_12_category_contact_sheet.png").exists()


def test_batch_ab_rejects_unexpected_manifest_fields(tmp_path):
    manifest, cases = _batch_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["private_upload_url"] = "https://example.invalid"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-12-invalid-schema"
    report = batch.run(manifest, output)

    assert report["status"] == "blocked"
    assert report["block_reasons"] == ["manifest_manifest_schema_invalid"]
    assert not (output / "ab_12_category_contact_sheet.png").exists()
