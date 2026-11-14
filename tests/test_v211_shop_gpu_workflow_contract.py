from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shop_gpu_evidence_requires_explicit_yes_and_dedicated_runner():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")

    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert "default: 'no'" in workflow
    assert "github.event.inputs.confirm_shop_gpu == 'yes'" in workflow
    assert "candidate_source_sha:" in workflow
    sha_input = workflow.split("      candidate_source_sha:", 1)[1].split("\n\npermissions:", 1)[0]
    assert "required: false" in sha_input
    assert "github.event.inputs.candidate_source_sha != ''" in workflow
    assert "contains(github.event.head_commit.message, '[shop-gpu-evidence yes candidate=')" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "git diff --name-only" in workflow
    assert "fetch-depth: 0" in workflow
    assert "docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md" in workflow
    assert "runs-on: [self-hosted, Windows, X64, niyom-shop-gpu]" in workflow
    assert "runs-on: windows-latest" not in workflow


def test_no_consent_path_has_hosted_status_and_cannot_schedule_shop_pc():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")
    status_job = workflow.split("  gate_status:", 1)[1].split("  evidence:", 1)[0]
    evidence_job = workflow.split("  evidence:", 1)[1]

    assert "runs-on: ubuntu-latest" in status_job
    assert "if:" not in status_job
    assert "runs-on: [self-hosted, Windows, X64, niyom-shop-gpu]" not in status_job
    assert "This hosted job only reports workflow status." in status_job
    assert "only by the evidence job after explicit consent and candidate SHA validation" in status_job
    assert "github.event.inputs.confirm_shop_gpu == 'yes'" in evidence_job
    assert "github.event.inputs.candidate_source_sha != ''" in evidence_job
    assert "runs-on: [self-hosted, Windows, X64, niyom-shop-gpu]" in evidence_job


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
    assert "Where-Object { $_ -notin $allowedFiles }" in workflow


def test_installed_candidate_may_only_differ_by_nonproduction_gate_files():
    workflow = _read(".github/workflows/v211-four-engine-manual-evidence.yml")
    allowed = workflow.split("$allowedFiles = @(", 1)[1].split(")", 1)[0]

    assert ".github/workflows/v211-four-engine-manual-evidence.yml" in allowed
    assert "tests/test_v211_shop_gpu_workflow_contract.py" in allowed
    assert "docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md" in allowed
    assert "signprint_ai/" not in allowed
    assert "tools/" not in allowed
    assert "Where-Object { $_ -notin $allowedFiles }" in workflow


def test_candidate_build_cancels_superseded_runs_for_the_current_branch():
    workflow = _read(".github/workflows/v211-four-engine-bridge-windows.yml")

    assert "group: niyomsil-v211-bridge-windows-${{ github.event.pull_request.head.ref || github.ref_name }}" in workflow
    assert "cancel-in-progress: true" in workflow

def test_candidate_build_uses_pr_head_commit_for_shop_evidence_identity():
    candidate = _read(".github/workflows/v211-four-engine-bridge-windows.yml")

    expected_ref = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
    assert "run-name: V2.1.1 Windows candidate - ${{ github.event.pull_request.head.sha || github.sha }}" in candidate
    assert candidate.count(expected_ref) == 2
    assert candidate.count("fetch-depth: 0") == 2
    assert "V211_EXPECTED_BASE_SHA: ${{ github.event.pull_request.base.sha }}" in candidate
    assert "V211_EXPECTED_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in candidate
    assert "v211_verify_candidate_provenance.ps1" in candidate
    assert "Parser]::ParseFile" in candidate
    verifier = _read("tools/v211_verify_candidate_provenance.ps1")
    assert "$checkoutSha = (git rev-parse HEAD).Trim().ToLowerInvariant()" in verifier
    assert "$proofCommit -ne $checkoutSha" in verifier
    assert "$proofCommit -ne $expectedHeadSha" in verifier
    assert "git merge-base --is-ancestor $expectedBaseSha $checkoutSha" in verifier
    assert "source_commit = $checkoutSha" in verifier
    assert "workflow_commit = $env:GITHUB_SHA" in verifier
    assert "BUILD_PROOF source commit does not match GITHUB_SHA" not in verifier

def test_candidate_provenance_verifier_resolves_base_sha_without_revision_suffix():
    verifier = _read("tools/v211_verify_candidate_provenance.ps1")

    assert "git cat-file -t $expectedBaseSha" in verifier
    assert "git fetch --no-tags origin $expectedBaseSha" in verifier
    assert "([string]$baseObjectType).Trim() -ne 'commit'" in verifier
    assert "git cat-file -e" not in verifier
    assert chr(92) + "${expectedBaseSha}" not in verifier
