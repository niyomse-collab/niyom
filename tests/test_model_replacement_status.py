"""Contracts for replacing every v1 external model before native ownership claims."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from native_models.model_replacement_status import build_report

ROOT = Path(__file__).resolve().parents[1]


def test_replacement_report_blocks_native_claim_until_all_models_are_replaced():
    report = build_report(ROOT)
    assert report["status"] == "in_progress_not_production_ready"
    assert report["native_claim_allowed"] is False
    assert report["roadmap_documented"] is True
    assert report["native_sr_code_present"] is True
    components = {item["v1_component"] for item in report["items"]}
    assert "RealESRGAN_x4plus.pth" in components
    assert "GFPGANv1.4.pth" in components
    assert "detection_Resnet50_Final.pth / RetinaFace / facexlib" in components
    assert all(item["production_ready"] is False for item in report["items"])


def test_replacement_status_cli_outputs_json(tmp_path):
    output = tmp_path / "native-status.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "native_models.model_replacement_status",
            "--repo-root",
            str(ROOT),
            "--output",
            str(output),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    printed = json.loads(result.stdout)
    written = json.loads(output.read_text("utf-8"))
    assert printed == written
    assert printed["native_claim_allowed"] is False
