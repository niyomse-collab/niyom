from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shop_gpu_evidence_requires_explicit_yes_and_dedicated_runner():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")

    assert "workflow_dispatch:" in workflow
    assert "default: 'no'" in workflow
    assert "inputs.confirm_shop_gpu == 'yes'" in workflow
    assert "runs-on: [self-hosted, Windows, X64, niyom-shop-gpu]" in workflow
    assert "runs-on: windows-latest" not in workflow


def test_candidate_regression_includes_the_shop_gpu_workflow_contract():
    workflow = _read(".github/workflows/v211-four-engine-bridge-windows.yml")

    assert "'tests/test_v211_*.py'" in workflow
    assert "'.github/workflows/v211-four-engine-manual-evidence.yml'" in workflow
    assert "tests/test_v211_shop_gpu_workflow_contract.py" in workflow


def test_shop_gpu_artifact_is_limited_to_json_evidence():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")
    start = workflow.index("- name: Upload JSON evidence only")
    end = workflow.index("- name: Remove local evidence workspace", start)
    upload_step = workflow[start:end]

    assert "v211-shop-evidence/build_identity.json" in upload_step
    assert "v211-shop-evidence/shop_gpu_diagnostic.json" in upload_step
    assert ".png" not in upload_step.lower()
    assert ".jpg" not in upload_step.lower()
    assert ".tif" not in upload_step.lower()


def test_synthetic_shop_gpu_evidence_never_certifies_visual_or_print_quality():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")

    assert "quality_improvement_verified -ne $false" in workflow
    assert "visual_quality_certified -ne $false" in workflow
    assert "print_quality_certified -ne $false" in workflow
    assert "customer_artwork_used -ne $false" in workflow
    assert "network_accessed -ne $false" in workflow
    assert "uploads_performed -ne $false" in workflow
    assert "images_retained -ne $false" in workflow
    assert "'runtime_device_use_verified'" in workflow
    assert "'shop_gpu_acceptance_passed'" in workflow
    assert "per_engine_runtime_device_use_verified" in workflow
    assert "$engineEvidence.Value -ne $true" in workflow
    assert "runtime_device_nvml_memory_verified_process_count" in workflow
    assert "runtime_device_wddm_pdh_verified_process_count" in workflow
    assert "runtime_gpu_engine_min_sample_count" in workflow
    assert "nvml_pid_plus_windows_gpu_engine_pdh" in workflow
    assert "bridge_integration.runtime_device_use_verified -ne $true" in workflow
