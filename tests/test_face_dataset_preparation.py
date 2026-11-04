"""Face datasets require explicit consent before native ownership claims."""
from __future__ import annotations

import csv
import json

import pytest
from PIL import Image

from native_models.prepare_face_dataset import generate, write_manifest


def _face_dataset(tmp_path):
    root = tmp_path / "private-faces"
    consent = tmp_path / "private-consent"
    consent.mkdir()
    colors_by_task = {
        "face_recovery": ((90, 80, 70), (120, 110, 100)),
        "face_detection": ((91, 80, 70), (121, 110, 100)),
    }
    for task, colors in colors_by_task.items():
        folder = root / task / "subject-a"
        folder.mkdir(parents=True)
        for idx, color in enumerate(colors):
            path = folder / f"{idx}.png"
            Image.new("RGB", (128, 128), color).save(path)
            if task == "face_detection":
                (folder / f"{idx}.png.json").write_text(
                    json.dumps({"face_bbox": "10,12,70,72"}),
                    "utf-8",
                )
    (consent / "subject-a.json").write_text(
        json.dumps({
            "subject_id": "subject-a",
            "consent_scope": "commercial_ai_training,internal_benchmark",
            "rights_holder": "Fixture subject",
        }),
        "utf-8",
    )
    return root, consent


def test_face_manifest_requires_consent_and_splits_by_task_and_subject(tmp_path):
    root, consent = _face_dataset(tmp_path)
    rows = generate(root, consent, seed=7)
    assert len(rows) == 4
    assert {row["task"] for row in rows} == {"face_recovery", "face_detection"}
    recovery_splits = {row["split"] for row in rows if row["task"] == "face_recovery"}
    detection_splits = {row["split"] for row in rows if row["task"] == "face_detection"}
    assert recovery_splits == {"train", "val"}
    assert detection_splits == {"train", "val"}
    assert all(
        row["consent_scope"].startswith("commercial_ai_training")
        for row in rows
    )
    assert all(row["rights_proof"].startswith("SHA256:") for row in rows)
    detector_rows = [row for row in rows if row["task"] == "face_detection"]
    assert {row["face_bbox"] for row in detector_rows} == {"10,12,70,72"}


def test_face_manifest_writes_csv_without_overwrite(tmp_path):
    root, consent = _face_dataset(tmp_path)
    rows = generate(root, consent)
    output = tmp_path / "face-manifest.csv"
    write_manifest(rows, output)
    with output.open("r", newline="", encoding="utf-8") as stream:
        written = list(csv.DictReader(stream))
    assert len(written) == len(rows)
    with pytest.raises(FileExistsError, match="overwrite"):
        write_manifest(rows, output)


def test_face_manifest_refuses_missing_commercial_ai_consent(tmp_path):
    root, consent = _face_dataset(tmp_path)
    (consent / "subject-a.json").write_text(
        json.dumps({
            "subject_id": "subject-a",
            "consent_scope": "display_only",
            "rights_holder": "Fixture subject",
        }),
        "utf-8",
    )
    with pytest.raises(ValueError, match="commercial_ai_training"):
        generate(root, consent)


def test_face_manifest_refuses_subject_mismatch(tmp_path):
    root, consent = _face_dataset(tmp_path)
    (consent / "subject-a.json").write_text(
        json.dumps({
            "subject_id": "other-subject",
            "consent_scope": "commercial_ai_training",
            "rights_holder": "Fixture subject",
        }),
        "utf-8",
    )
    with pytest.raises(ValueError, match="does not match"):
        generate(root, consent)


def test_face_manifest_refuses_bad_detector_bbox(tmp_path):
    root, consent = _face_dataset(tmp_path)
    sidecar = root / "face_detection" / "subject-a" / "0.png.json"
    sidecar.write_text(json.dumps({"face_bbox": "10,10,-1,50"}), "utf-8")
    with pytest.raises(ValueError, match="positive"):
        generate(root, consent)


def test_face_manifest_refuses_duplicate_face_content(tmp_path):
    root, consent = _face_dataset(tmp_path)
    duplicate = root / "face_recovery" / "subject-a" / "duplicate.png"
    duplicate.write_bytes((root / "face_recovery" / "subject-a" / "0.png").read_bytes())
    with pytest.raises(ValueError, match="Duplicate face image"):
        generate(root, consent)
