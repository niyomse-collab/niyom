"""V2 production packaging is blocked until all native model proofs pass."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from native_models.production_gate import validate_release


def _model(root, model_id, *, status="approved_for_production"):
    folder = root / model_id
    folder.mkdir(parents=True)
    checkpoint = folder / "model.pth"
    content = f"{model_id}:fixture".encode("utf-8")
    checkpoint.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    (folder / "TRAINING_PROVENANCE.json").write_text(
        json.dumps({
            "model_id": model_id,
            "status": status,
            "training_origin": "random_initialization_no_upstream_checkpoint",
            "checkpoint": checkpoint.name,
            "train_files": 10,
            "validation_files": 2,
            "inventory_sha256": "a" * 64,
            "checkpoint_sha256": digest,
            "rights_review_sha256": "b" * 64,
        }),
        "utf-8",
    )


def test_production_gate_requires_all_three_native_models(tmp_path):
    _model(tmp_path, "niyomsil-sr-v1")
    with pytest.raises(FileNotFoundError, match="niyomsil-detector-v1"):
        validate_release(tmp_path)


def test_production_gate_accepts_complete_approved_release(tmp_path):
    for model_id in ("niyomsil-sr-v1", "niyomsil-face-v1", "niyomsil-detector-v1"):
        _model(tmp_path, model_id)
    report = validate_release(tmp_path)
    assert report["production_release_allowed"] is True
    assert sorted(report["models"]) == [
        "niyomsil-detector-v1",
        "niyomsil-face-v1",
        "niyomsil-sr-v1",
    ]


def test_production_gate_rejects_print_review_only_model(tmp_path):
    _model(tmp_path, "niyomsil-sr-v1")
    _model(tmp_path, "niyomsil-face-v1", status="approved_for_print_review")
    _model(tmp_path, "niyomsil-detector-v1")
    with pytest.raises(ValueError, match="production"):
        validate_release(tmp_path)


def test_production_gate_cli_outputs_json(tmp_path):
    for model_id in ("niyomsil-sr-v1", "niyomsil-face-v1", "niyomsil-detector-v1"):
        _model(tmp_path, model_id)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "native_models.production_gate",
            "--models-root",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout)["production_release_allowed"] is True
