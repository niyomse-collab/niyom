"""Block v2 production packaging until every native model is approved."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_models.validate_provenance import NATIVE_TARGETS, validate


def validate_model_dir(model_dir: Path) -> dict:
    provenance = model_dir / "TRAINING_PROVENANCE.json"
    summary = validate(provenance, require_production=True)
    return {**summary, "provenance": str(provenance)}


def validate_release(models_root: Path) -> dict:
    if not models_root.is_dir():
        raise FileNotFoundError(f"Missing native models root: {models_root}")
    summaries = {}
    for model_id in sorted(NATIVE_TARGETS):
        model_dir = models_root / model_id
        if not model_dir.is_dir():
            raise FileNotFoundError(f"Missing required native model directory: {model_dir}")
        summary = validate_model_dir(model_dir)
        if summary["model_id"] != model_id:
            raise ValueError(
                f"Provenance model_id {summary['model_id']} does not match {model_id}"
            )
        summaries[model_id] = summary
    return {
        "production_release_allowed": True,
        "required_models": sorted(NATIVE_TARGETS),
        "models": summaries,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate all native models before v2 production packaging")
    parser.add_argument("--models-root", required=True)
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    report = validate_release(Path(args.models_root))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
