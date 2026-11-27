from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "Run-V211-ShopGPU-Diagnostic.ps1"
AUTHORIZED_CANDIDATE = "518295b03292ed49f3231e97be1bd62246501380"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_local_gpu_diagnostic_is_pinned_to_exact_candidate_1123():
    source = _source()
    assert AUTHORIZED_CANDIDATE in source
    assert "BUILD_PROOF.txt" in source
    assert "Source commit:" in source
    assert "installedSourceSha -ne $ExpectedCandidateSha" in source


def test_local_gpu_diagnostic_uses_packaged_synthetic_only_command():
    source = _source()
    assert "--diagnose-v211-four-ai" in source
    assert "--manifest" in source
    assert "--output-dir" in source
    assert "--timeout-seconds" in source
    assert "shop_gpu_diagnostic.json" in source
    for engine in ("anime4k", "real_cugan", "real_esrgan", "waifu2x"):
        assert engine in source


def test_local_gpu_diagnostic_never_downloads_or_uploads_and_disables_image_retention():
    source = _source().casefold()
    for forbidden in (
        "invoke-webrequest",
        "invoke-restmethod",
        "start-bitstransfer",
        "upload-artifact",
        "gh run",
        "git push",
        "curl.exe",
    ):
        assert forbidden not in source
    assert "niyomsil_v211_four_ai_evidence_dir" in source
    assert "customer_artwork_used" in source
    assert "network_accessed" in source
    assert "uploads_performed" in source


def test_local_gpu_diagnostic_keeps_output_outside_install_and_model_folders():
    source = _source()
    assert "$installPrefix" in source
    assert "$manifestPrefix" in source
    assert "$OutputDirectory.StartsWith" in source
    assert "SetEnvironmentVariable" in source


def test_local_gpu_diagnostic_refuses_to_overwrite_existing_qa_files():
    source = _source()
    inspect_output = source.index("Get-ChildItem -LiteralPath $OutputDirectory -Force")
    create_output = source.index("[System.IO.Directory]::CreateDirectory($OutputDirectory)")
    assert inspect_output < create_output
    assert "must be new or empty" in source
