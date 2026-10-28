"""Audit v2 progress toward replacing v1 external model weights.

This reports ownership/provenance status only. It never approves production use
and never claims that renamed third-party weights are native NiyomSilp models.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReplacementItem:
    capability: str
    v1_component: str
    native_target: str
    current_status: str
    production_ready: bool
    blocking_reason: str
    next_step: str


def default_items() -> list[ReplacementItem]:
    return [
        ReplacementItem(
            capability="sign_super_resolution",
            v1_component="RealESRGAN_x4plus.pth",
            native_target="niyomsil-sr-v1",
            current_status="native_training_pipeline_started",
            production_ready=False,
            blocking_reason="No shop-trained checkpoint has passed validation and print review.",
            next_step="Train from a rights-checked manifest, run v2 outputs, then evaluate against v1.",
        ),
        ReplacementItem(
            capability="face_recovery_studio",
            v1_component="GFPGANv1.4.pth",
            native_target="niyomsil-face-v1",
            current_status="not_started",
            production_ready=False,
            blocking_reason="No consented face dataset, architecture, checkpoint or identity benchmark exists yet.",
            next_step="Define face dataset consent rules and a separate portrait model training/evaluation path.",
        ),
        ReplacementItem(
            capability="face_detection_selection",
            v1_component="detection_Resnet50_Final.pth / RetinaFace / facexlib",
            native_target="niyomsil-detector-v1",
            current_status="not_started",
            production_ready=False,
            blocking_reason="Detector still depends on external RetinaFace/facexlib checkpoint.",
            next_step="Choose a rights-clear detector path or train a native detector with provenance.",
        ),
    ]


def build_report(repo_root: Path) -> dict:
    items = default_items()
    docs = repo_root / "docs" / "NIYOMSIL_NATIVE_MODEL_ROADMAP_TH.md"
    native_sr = repo_root / "native_models" / "niyomsil_sr.py"
    face_manifest = repo_root / "native_models" / "prepare_face_dataset.py"
    return {
        "status": "in_progress_not_production_ready",
        "native_claim_allowed": False,
        "reason": (
            "At least one v1 AI capability still depends on external model weights. "
            "Only checkpoints trained from random initialization or supported by explicit rights "
            "documents may be called native NiyomSilp models."
        ),
        "roadmap_documented": docs.is_file(),
        "native_sr_code_present": native_sr.is_file(),
        "face_consent_manifest_code_present": face_manifest.is_file(),
        "items": [asdict(item) for item in items],
    }


def main():
    parser = argparse.ArgumentParser(description="Report v2 native model replacement status")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", help="Optional local JSON report path")
    args = parser.parse_args()
    report = build_report(Path(args.repo_root))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
