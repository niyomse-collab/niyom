"""V2 provenance and separation contracts; no GPU/model checkpoint required in CI."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_experimental_v2_finetune_is_explicitly_derivative():
    source = (ROOT / "native_models" / "finetune_realesrgan.py").read_text("utf-8")
    ast.parse(source)
    assert 'MODEL_ID = "niyomsil-sign-ai-v2"' in source
    assert "RealESRGAN_x4plus" in source
    assert "FINE_TUNED_FROM_THIRD_PARTY_PRETRAINED_WEIGHTS" in source
    assert "load_state_dict" in source
    assert "weights_only=True" in source
    assert "pretrained-sha256" in source
    assert "allow-pretrained-derivative" in source
    assert "base_validation_psnr" in source
    assert "bicubic_validation_psnr" in source
    assert "PROVENANCE_V2.json" in source


def test_v2_training_requires_human_rights_and_private_images():
    source = (ROOT / "native_models" / "finetune_realesrgan.py").read_text("utf-8")
    for field in ("rights_review", "commercial_use_approved",
                  "dataset_rights_confirmed", "upstream_checkpoint_url",
                  "upstream_checkpoint_license", "rights_review_sha256",
                  "training_manifest_sha256"):
        assert field in source
    base = (ROOT / "native_models" / "train_sr.py").read_text("utf-8")
    assert 'REQUIRED = {"relative_path", "rights_holder", "license", "rights_proof", "sha256", "split"}' in base
    assert "data leakage" in base
    ignore = (ROOT / ".gitignore").read_text("utf-8")
    assert "training_data/" in ignore
    assert "training_runs/" in ignore


def test_v1_frozen_while_v2_is_experimental():
    v1 = (ROOT / "signprint_ai" / "independent_core.py").read_text("utf-8")
    assert '"RealESRGAN_x4plus.pth"' in v1
    assert "native_models.finetune_realesrgan" not in v1
    install = (ROOT / "installer.iss").read_text("utf-8")
    assert '#define MyAppName "NiyomSilp Design v1"' in install
    assert '#define MyAppVersion "1.0.1"' in install
    docs = (ROOT / "docs" / "V2_MODEL_RIGHTS_TH.md").read_text("utf-8")
    assert "FINE_TUNED" not in docs or "pretrained" in docs.lower()


def test_provenance_metadata_fields_documented():
    src = (ROOT / "native_models" / "finetune_realesrgan.py").read_text("utf-8")
    tree = ast.parse(src)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "load_base_checkpoint"
               for node in tree.body)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "evaluate"
               for node in tree.body)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "run"
               for node in tree.body)


def test_native_model_roadmap_names_all_v1_external_models():
    roadmap = (ROOT / "docs" / "NIYOMSIL_NATIVE_MODEL_ROADMAP_TH.md").read_text("utf-8")
    for name in (
        "RealESRGAN_x4plus.pth",
        "GFPGANv1.4.pth",
        "detection_Resnet50_Final.pth",
        "niyomsil-sr-v1",
        "niyomsil-face-v1",
        "provenance JSON",
    ):
        assert name in roadmap
    assert "ไม่ทำให้เป็นเจ้าของลิขสิทธิ์โมเดล" in roadmap
    assert "ยังไม่มีน้ำหนักโมเดลนิยมศิลป์ที่ฝึกเสร็จ" in roadmap
