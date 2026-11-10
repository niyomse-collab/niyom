from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shop_gpu_evidence_requires_explicit_yes_and_dedicated_runner():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")

    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert "default: 'no'" in workflow
    assert "inputs.confirm_shop_gpu == 'yes'" in workflow
    assert "candidate_source_sha:" in workflow
    assert "inputs.candidate_source_sha != ''" in workflow
    assert "contains(github.event.head_commit.message, '[shop-gpu-evidence yes candidate=')" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "git diff --name-only" in workflow
    assert "fetch-depth: 0" in workflow
    assert "docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md" in workflow
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
    assert "runtime_gpu_engine_adapter_luid_match" in workflow
    assert "runtime_gpu_engine_adapter_luid" in workflow
    assert "0x[0-9a-fA-F]{8}_0x[0-9a-fA-F]{8}" in workflow
    assert "nvml_pid_plus_windows_gpu_engine_pdh" in workflow
    assert "bridge_integration.runtime_device_use_verified -ne $true" in workflow

def test_premerge_push_gate_is_branch_scoped_and_candidate_pinned():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")

    assert "branches:" in workflow
    assert "- work/v211-four-engine-v2-bridge-20261103" in workflow
    assert "'.github/workflows/v211-four-engine-manual-evidence.yml'" in workflow
    assert "'docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md'" in workflow
    assert r"\[shop-gpu-evidence\s+yes\s+candidate=([0-9a-fA-F]{40})\]" in workflow
    assert "git cat-file -e" in workflow
    assert "Candidate source SHA must be exactly 40 hexadecimal characters." in workflow
    assert "$unexpectedFiles.Count -gt 0" in workflow
    assert "Where-Object { $_ -ne 'docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md' }" in workflow

def test_installed_candidate_may_only_differ_by_nonproduction_gate_files():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")
    allowed = workflow.split("$allowedFiles = @(", 1)[1].split(")", 1)[0]

    assert ".github/workflows/v211-four-engine-manual-evidence.yml" in allowed
    assert "tests/test_v211_shop_gpu_workflow_contract.py" in allowed
    assert "docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md" in allowed
    assert "signprint_ai/" not in allowed
    assert "tools/" not in allowed
    assert "Where-Object { $_ -notin $allowedFiles }" in workflow
