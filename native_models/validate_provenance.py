"""Validate provenance records before treating v2 checkpoints as native models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

NATIVE_TARGETS = {
    "niyomsil-sr-v1",
    "niyomsil-face-v1",
    "niyomsil-detector-v1",
}
OWNED_ORIGINS = {
    "random_initialization_no_upstream_checkpoint",
    "explicit_rights_transferred_base_weights",
}
REQUIRED_FIELDS = {
    "model_id",
    "status",
    "training_origin",
    "train_files",
    "validation_files",
    "inventory_sha256",
    "checkpoint_sha256",
    "rights_review_sha256",
}
APPROVED_STATUSES = {"approved_for_print_review", "approved_for_production"}


def _read(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing provenance file: {path}")
    try:
        payload = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Provenance must be JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Provenance must be a JSON object")
    return payload


def validate(path: Path, *, require_production: bool = False) -> dict:
    """Return a normalized approval summary or raise ValueError."""
    payload = _read(path)
    missing = sorted(field for field in REQUIRED_FIELDS if not payload.get(field))
    if missing:
        raise ValueError(f"Missing provenance fields: {', '.join(missing)}")
    model_id = str(payload["model_id"])
    if model_id not in NATIVE_TARGETS:
        raise ValueError(f"Unknown native model target: {model_id}")
    origin = str(payload["training_origin"])
    if origin not in OWNED_ORIGINS:
        raise ValueError(
            "Training origin is not eligible for native ownership claims: "
            f"{origin}"
        )
    status = str(payload["status"])
    if status not in APPROVED_STATUSES:
        raise ValueError(f"Model is not approved for release: {status}")
    if require_production and status != "approved_for_production":
        raise ValueError("Model is not approved for production")
    train_files = int(payload["train_files"])
    validation_files = int(payload["validation_files"])
    if train_files <= 0 or validation_files <= 0:
        raise ValueError("Provenance must include train and validation files")
    return {
        "model_id": model_id,
        "status": status,
        "native_claim_allowed": True,
        "production_ready": status == "approved_for_production",
        "training_origin": origin,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate native model provenance JSON")
    parser.add_argument("provenance")
    parser.add_argument("--require-production", action="store_true")
    args = parser.parse_args()
    summary = validate(Path(args.provenance), require_production=args.require_production)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
