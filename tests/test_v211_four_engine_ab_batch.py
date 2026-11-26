import json
from pathlib import Path

from PIL import Image, ImageCms

from tools import v211_four_engine_ab_batch as batch
from tools.v211_four_engine_ab_report import ENGINES, REVIEW_REGION_LABELS, sha256_file


_SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _fixture(tmp_path, *, with_icc=True):
    profile = _SRGB_PROFILE if with_icc else None
    source = tmp_path / "source.png"
    v2 = tmp_path / "accepted-v2.png"
    candidate = tmp_path / "qa-candidate.png"
    evidence = tmp_path / "candidate.qa.json"
    Image.new("RGB", (16, 12), (20, 40, 60)).save(source, format="PNG")
    alpha = Image.new("L", (32, 24), 255)
    for y in range(5, 19):
        for x in range(7, 25):
            alpha.putpixel((x, y), 0 if (x + y) % 4 == 0 else 180)
    base = Image.new("RGBA", (32, 24), (120, 60, 30, 255))
    base.putalpha(alpha)
    base.save(v2, format="PNG", dpi=(300, 300), icc_profile=profile)
    changed = base.copy()
    pixels = changed.load()
    for y in range(8, 15):
        for x in range(10, 21):
            red, green, blue, opacity = pixels[x, y]
            pixels[x, y] = (min(255, red + 5), green, blue, opacity)
    changed.save(candidate, format="PNG", dpi=(300, 300), icc_profile=profile)
    alpha.close()
    base.close()
    changed.close()
    evidence.write_text(json.dumps({
        "schema_version": 1,
        "evidence_type": "niyomsil_v211_four_engine_qa",
        "source_v2_pair_bound_by_bridge": True,
        "source_sha256": sha256_file(source),
        "v2_reference_sha256": sha256_file(v2),
        "qa_image_sha256": sha256_file(candidate),
        "native_seed_sha256": "1" * 64,
        "native_v2_reference_sha256": "2" * 64,
        "fusion_output_sha256": "3" * 64,
        "engine_candidate_sha256": {
            name: str(index + 4) * 64 for index, name in enumerate(ENGINES)
        },
        "completed_engine_count": 4,
        "completed_engine_names": list(ENGINES),
        "per_engine_runtime_device_use_verified": {name: True for name in ENGINES},
        "runtime_device_use_verified": True,
        "fusion_implemented": True,
        "all_four_engine_candidates_consumed": True,
        "all_four_engine_pixels_contributed": True,
        "engine_pixel_effect_verified": {name: True for name in ENGINES},
        "engine_pixel_effect_pixels": {name: 7 for name in ENGINES},
        "v2_output_preserved": True,
        "quality_certified": False,
        "privacy": {
            "paths_included": False, "commands_included": False,
            "logs_included": False, "image_pixels_included": False,
        },
    }), encoding="utf-8")
    return source, v2, candidate, evidence


def _batch_manifest(tmp_path, *, omit=None, untagged_labels=()):
    cases = []
    inputs = tmp_path / "inputs"
    for label in REVIEW_REGION_LABELS:
        if label == omit:
            continue
        folder = inputs / label
        folder.mkdir(parents=True, exist_ok=True)
        source, v2, candidate, evidence = _fixture(
            folder, with_icc=label not in set(untagged_labels)
        )
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
    input_paths = [
        (tmp_path / case[key]).resolve()
        for case in cases
        for key in ("source", "v2_reference", "candidate", "evidence")
    ]
    hashes_before = {path: sha256_file(path) for path in input_paths}
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
    contact_sheet_path = output / "ab_12_category_contact_sheet.png"
    assert contact_sheet_path.is_file()
    with Image.open(contact_sheet_path) as contact_sheet:
        with Image.open(output / REVIEW_REGION_LABELS[0] / f"ab_crop_01_{REVIEW_REGION_LABELS[0]}.png") as crop:
            assert contact_sheet.info.get("icc_profile") == crop.info.get("icc_profile")
    assert report["category_contact_sheet_status"] == "created"
    assert (output / "ab_12_category_report.json").is_file()
    for label in REVIEW_REGION_LABELS:
        assert (output / label / f"ab_crop_01_{label}.png").is_file()
    persisted = (output / "ab_12_category_report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in persisted
    assert all(sha256_file(path) == digest for path, digest in hashes_before.items())


def test_batch_ab_skips_aggregate_sheet_when_category_icc_profiles_differ(tmp_path):
    manifest, cases = _batch_manifest(
        tmp_path, untagged_labels={"thai_pattern"}
    )
    output = tmp_path / "ab-12-mixed-icc"

    report = batch.run(manifest, output)

    assert report["status"] == "ready_for_human_review"
    assert report["all_12_categories_ready_for_human_review"] is True
    assert report["category_contact_sheet_status"] == "skipped_mixed_icc_profiles"
    assert "category_contact_sheet_mixed_icc_profiles" in report["warnings"]
    assert not (output / "ab_12_category_contact_sheet.png").exists()
    case_by_label = {case["label"]: case for case in cases}
    for label in REVIEW_REGION_LABELS:
        crop_path = output / label / f"ab_crop_01_{label}.png"
        v2_path = tmp_path / case_by_label[label]["v2_reference"]
        assert crop_path.is_file()
        with Image.open(crop_path) as crop, Image.open(v2_path) as reference:
            # Mixed ICC prevents one aggregate profile, but each individual
            # review crop must retain its own accepted-V2 profile (or None).
            assert crop.info.get("icc_profile") == reference.info.get("icc_profile")


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
