"""Native model provenance must reject renamed or derivative checkpoints."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from native_models.validate_provenance import validate


def _record(checkpoint_hash: str, **updates):
    data = {
        "model_id": "niyomsil-sr-v1",
        "status": "approved_for_print_review",
        "training_origin": "random_initialization_no_upstream_checkpoint",
        "checkpoint": "model.pth",
        "train_files": 12,
        "validation_files": 4,
        "inventory_sha256": "a" * 64,
        "checkpoint_sha256": checkpoint_hash,
        "rights_review_sha256": "c" * 64,
    }
    data.update(updates)
    return data


def _write_checkpoint(tmp_path, content=b"native checkpoint fixture"):
    import hashlib

    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def test_validate_accepts_owned_native_provenance(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "TRAINING_PROVENANCE.json"
    path.write_text(json.dumps(_record(checkpoint_hash)), "utf-8")
    summary = validate(path)
    assert summary["native_claim_allowed"] is True
    assert summary["production_ready"] is False
    assert summary["checkpoint_sha256"] == checkpoint_hash


def test_validate_rejects_derivative_pretrained_origin(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "PROVENANCE_V2.json"
    path.write_text(
        json.dumps(_record(
            checkpoint_hash,
            training_origin="FINE_TUNED_FROM_THIRD_PARTY_PRETRAINED_WEIGHTS",
        )),
        "utf-8",
    )
    with pytest.raises(ValueError, match="not eligible"):
        validate(path)


def test_validate_rejects_experimental_status(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "TRAINING_PROVENANCE.json"
    path.write_text(
        json.dumps(_record(checkpoint_hash, status="experimental_NOT_approved_for_production")),
        "utf-8",
    )
    with pytest.raises(ValueError, match="not approved"):
        validate(path)


def test_validate_can_require_production_approval(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "TRAINING_PROVENANCE.json"
    path.write_text(json.dumps(_record(checkpoint_hash)), "utf-8")
    with pytest.raises(ValueError, match="production"):
        validate(path, require_production=True)
    path.write_text(
        json.dumps(_record(checkpoint_hash, status="approved_for_production")),
        "utf-8",
    )
    assert validate(path, require_production=True)["production_ready"] is True


def test_validate_rejects_checkpoint_hash_mismatch(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "TRAINING_PROVENANCE.json"
    path.write_text(json.dumps(_record(checkpoint_hash)), "utf-8")
    (tmp_path / "model.pth").write_bytes(b"changed after approval")
    with pytest.raises(ValueError, match="SHA256"):
        validate(path)


def test_validate_cli_outputs_json(tmp_path):
    checkpoint_hash = _write_checkpoint(tmp_path)
    path = tmp_path / "TRAINING_PROVENANCE.json"
    path.write_text(
        json.dumps(_record(checkpoint_hash, model_id="niyomsil-detector-v1")),
        "utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "native_models.validate_provenance", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout)["model_id"] == "niyomsil-detector-v1"
