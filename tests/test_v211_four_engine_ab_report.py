"""Evidence-bound local A/B report tests; never certify visual quality."""
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image, ImageCms

from tools import v211_four_engine_ab_report as ab_report
from tools.v211_four_engine_ab_report import ENGINES, run


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture(tmp_path, *, alpha_match=True, icc_match=True, dpi_match=True):
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source, v2, candidate = (
        tmp_path / "source.png", tmp_path / "accepted-v2.png", tmp_path / "qa-candidate.png"
    )
    alpha = Image.new("L", (32, 24), 255)
    for y in range(5, 19):
        for x in range(7, 25):
            alpha.putpixel((x, y), 0 if (x + y) % 4 == 0 else 180)
    Image.new("RGB", (16, 12), (20, 40, 60)).save(source)
    base = Image.new("RGBA", (32, 24), (120, 60, 30, 255))
    base.putalpha(alpha)
    base.save(v2, format="PNG", dpi=(300, 300), icc_profile=profile)
    changed = base.copy()
    pixels = changed.load()
    for y in range(8, 15):
        for x in range(10, 21):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (min(255, r + 5), g, b, a)
    if not alpha_match:
        changed.putpixel((2, 2), (120, 60, 30, 0))
    changed.save(
        candidate, format="PNG",
        dpi=(300, 300) if dpi_match else (150, 150),
        icc_profile=profile if icc_match else None,
    )
    alpha.close()
    base.close()
    changed.close()
    evidence = tmp_path / "candidate.qa.json"
    evidence.write_text(json.dumps({
        "schema_version": 1,
        "evidence_type": "niyomsil_v211_four_engine_qa",
        "source_v2_pair_bound_by_bridge": True,
        "source_sha256": _sha(source),
        "v2_reference_sha256": _sha(v2),
        "qa_image_sha256": _sha(candidate),
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


def test_ab_report_creates_private_human_review_pack_without_quality_claims(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    hashes_before = (_sha(source), _sha(v2), _sha(candidate))
    output = tmp_path / "ab-review"
    report = run(source, v2, candidate, evidence, output)

    assert report["status"] == "ready_for_human_review"
    assert report["source_v2_pair_bound_by_bridge"] is True
    assert report["evidence_metadata_consistent"] is True
    assert report["evidence_verified"] is False
    assert report["evidence_authenticity_verified"] is False
    assert report["same_source_generation_proven"] is False
    assert report["quality_certified"] is False
    assert report["visual_quality_certified"] is False
    assert report["print_quality_certified"] is False
    assert report["human_review_required"] is True
    assert report["metrics"]["alpha_exact_match"] is True
    assert report["metrics"]["changed_visible_pixels"] > 0
    assert report["icc_profile_match"] is True
    assert report["dpi_match"] is True
    assert "ab_contact_sheet.png" in report["artifacts"]
    assert (output / "ab_contact_sheet.png").is_file()
    assert any(name.startswith("ab_crop_") for name in report["artifacts"])
    persisted = (output / "ab_report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in persisted
    assert hashes_before == (_sha(source), _sha(v2), _sha(candidate))


def test_ab_report_fails_closed_when_physical_gpu_evidence_is_incomplete(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["per_engine_runtime_device_use_verified"]["waifu2x"] = False
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-no-gpu-proof"
    report = run(source, v2, candidate, evidence, output)
    assert report["status"] == "blocked"
    assert "physical_gpu_adapter_not_verified_for_all_engines" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()
    assert report["quality_certified"] is False


def test_ab_report_fails_closed_when_any_engine_has_no_pixel_effect(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["engine_pixel_effect_verified"]["waifu2x"] = False
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-no-waifu-pixel-effect"
    report = run(source, v2, candidate, evidence, output)
    assert report["status"] == "blocked"
    assert "engine_pixel_effect_not_verified_for_all_engines" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_fails_closed_when_engine_pixel_effect_count_is_zero(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["engine_pixel_effect_pixels"]["anime4k"] = 0
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-zero-anime4k-contribution"
    report = run(source, v2, candidate, evidence, output)
    assert report["status"] == "blocked"
    assert "engine_pixel_effect_pixels_incomplete" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_fails_closed_when_engine_name_manifest_contains_unhashable_values(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["completed_engine_names"][-1] = {"unexpected": "mapping"}
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-unhashable-engine-name"

    report = run(source, v2, candidate, evidence, output)

    assert report["status"] == "blocked"
    assert "four_native_engines_not_complete" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_requires_an_integer_engine_count(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["completed_engine_count"] = 4.0
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ab-non-integer-engine-count"

    report = run(source, v2, candidate, evidence, output)

    assert report["status"] == "blocked"
    assert "four_native_engines_not_complete" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_blocks_alpha_mismatch(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path, alpha_match=False)
    output = tmp_path / "ab-alpha-mismatch"
    report = run(source, v2, candidate, evidence, output)
    assert report["status"] == "blocked"
    assert "alpha_not_pixel_identical_to_accepted_v2" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_blocks_icc_and_dpi_mismatch(tmp_path):
    source, v2, candidate, evidence = _fixture(
        tmp_path, icc_match=False, dpi_match=False
    )
    output = tmp_path / "ab-metadata-mismatch"
    report = run(source, v2, candidate, evidence, output)
    assert report["status"] == "blocked"
    assert "icc_profile_mismatch" in report["block_reasons"]
    assert "print_dpi_mismatch" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_rejects_output_inside_repository(tmp_path):
    source, v2, candidate, evidence = _fixture(tmp_path)
    repository_root = Path(__file__).resolve().parents[1]
    try:
        run(source, v2, candidate, evidence, repository_root / "ab-private-test-output")
    except ValueError as exc:
        assert "outside the Git repository" in str(exc)
    else:
        raise AssertionError("A/B artifacts must never be written into the repository")


def _write_tiff_reference(v2_png: Path, tiff_path: Path, *, bigtiff=False):
    with Image.open(v2_png) as image:
        pixels = np.asarray(image).copy()
        profile = image.info.get("icc_profile")
        dpi = image.info.get("dpi")
    options = {
        "photometric": "rgb",
        "planarconfig": "contig",
        "resolution": tuple(float(value) for value in dpi),
        "resolutionunit": "INCH",
        "iccprofile": profile,
        "metadata": None,
        "bigtiff": bigtiff,
    }
    if pixels.shape[-1] == 4:
        options["extrasamples"] = "unassalpha"
    tifffile.imwrite(tiff_path, pixels, **options)
    return tiff_path


def _rebind_v2_evidence(evidence: Path, v2_reference: Path):
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["v2_reference_sha256"] = _sha(v2_reference)
    evidence.write_text(json.dumps(payload), encoding="utf-8")


def test_ab_report_accepts_single_page_tiff_v2_reference_against_png_candidate(
    tmp_path, monkeypatch
):
    source, v2_png, candidate, evidence = _fixture(tmp_path)
    v2_tiff = _write_tiff_reference(v2_png, tmp_path / "accepted-v2.tif")
    _rebind_v2_evidence(evidence, v2_tiff)
    hashes_before = (_sha(source), _sha(v2_tiff), _sha(candidate))
    output = tmp_path / "ab-tiff-review"

    report = run(source, v2_tiff, candidate, evidence, output)

    assert report["status"] == "ready_for_human_review"
    assert report["v2_reference_format"] == "TIFF"
    assert report["v2_reference_is_bigtiff"] is False
    assert report["candidate_format"] == "PNG"
    assert report["tiff_region_access"] is True
    assert report["metrics"]["alpha_exact_match"] is True
    assert report["icc_profile_match"] is True
    assert report["dpi_match"] is True
    assert report["quality_certified"] is False
    assert (output / "ab_contact_sheet.png").is_file()
    assert hashes_before == (_sha(source), _sha(v2_tiff), _sha(candidate))


def test_ab_report_accepts_bigtiff_v2_reference_with_forced_streaming(
    tmp_path, monkeypatch
):
    source, v2_png, candidate, evidence = _fixture(tmp_path)
    v2_bigtiff = _write_tiff_reference(
        v2_png, tmp_path / "accepted-v2-bigtiff.tif", bigtiff=True
    )
    _rebind_v2_evidence(evidence, v2_bigtiff)
    monkeypatch.setattr(ab_report, "MAX_RGBA_VALIDATION_PIXELS", 1)
    output = tmp_path / "ab-bigtiff-review"

    report = run(source, v2_bigtiff, candidate, evidence, output)

    assert report["status"] == "ready_for_human_review"
    assert report["v2_reference_format"] == "TIFF"
    assert report["v2_reference_is_bigtiff"] is True
    assert report["streamed_large_image"] is True
    assert report["streamed_raster_access"] is True
    assert report["metrics"]["alpha_exact_match"] is True
    assert report["quality_certified"] is False
    assert (output / "ab_contact_sheet.png").is_file()


def test_ab_report_rejects_multipage_tiff_v2_reference(tmp_path):
    source, v2_png, candidate, evidence = _fixture(tmp_path)
    pixels = np.zeros((24, 32, 3), dtype=np.uint8)
    v2_tiff = tmp_path / "accepted-v2-multipage.tif"
    with tifffile.TiffWriter(v2_tiff) as writer:
        writer.write(pixels, photometric="rgb", metadata=None)
        writer.write(pixels, photometric="rgb", metadata=None)
    _rebind_v2_evidence(evidence, v2_tiff)
    output = tmp_path / "ab-multipage-blocked"

    report = run(source, v2_tiff, candidate, evidence, output)

    assert report["status"] == "blocked"
    assert "image_preflight_abreporterror" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()


def test_ab_report_rejects_16bit_tiff_v2_reference(tmp_path):
    source, v2_png, candidate, evidence = _fixture(tmp_path)
    pixels = np.zeros((24, 32, 3), dtype=np.uint16)
    v2_tiff = tmp_path / "accepted-v2-16bit.tif"
    tifffile.imwrite(v2_tiff, pixels, photometric="rgb", metadata=None)
    _rebind_v2_evidence(evidence, v2_tiff)
    output = tmp_path / "ab-16bit-blocked"

    report = run(source, v2_tiff, candidate, evidence, output)

    assert report["status"] == "blocked"
    assert "image_preflight_abreporterror" in report["block_reasons"]
    assert not (output / "ab_contact_sheet.png").exists()
