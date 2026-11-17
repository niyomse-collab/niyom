from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shop_runner_readiness_script_is_read_only_and_profile_scoped():
    script = (ROOT / "tools" / "Test-V211-ShopRunner.ps1").read_text(encoding="utf-8")

    assert "[CmdletBinding()]" in script
    assert "Win32_Service" in script
    assert "Win32_Process" in script
    assert "Runner.Listener.exe" in script
    assert "HKCU:\\" in script
    assert "Inno Setup: App Path" in script
    assert "BUILD_PROOF.txt" in script
    assert "LocalApplicationData" in script
    assert "NiyomSilp\\V211-FourAI-QA\\manifest.json" in script
    assert "nvidia-smi.exe" in script
    assert "vulkan-1.dll" in script
    assert "niyom-shop-gpu" in script
    assert "github_runner_labels_verified_locally = $false" in script
    assert "manifest_hashes_verified = $false" in script
    assert "network_accessed = $false" in script
    assert "model_downloaded = $false" in script
    assert "customer_artwork_accessed = $false" in script
    assert "files_written = $false" in script
    assert "services_changed = $false" in script
    assert "ConvertTo-Json -Depth 8" in script


def test_shop_runner_readiness_script_contains_no_mutating_or_network_commands():
    script = (ROOT / "tools" / "Test-V211-ShopRunner.ps1").read_text(encoding="utf-8")
    forbidden = (
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        "Start-Process",
        "Start-Service",
        "Stop-Service",
        "Restart-Service",
        "Set-Service",
        "Set-ItemProperty",
        "New-ItemProperty",
        "Remove-ItemProperty",
        "Remove-Item",
        "Set-Content",
        "Add-Content",
        "Out-File",
        "WriteAllText",
        "WriteAllBytes",
        "Register-ScheduledTask",
        "Unregister-ScheduledTask",
    )
    lowered = script.casefold()
    assert all(command.casefold() not in lowered for command in forbidden)


def test_shop_runner_readiness_script_does_not_claim_labels_or_hash_verification():
    script = (ROOT / "tools" / "Test-V211-ShopRunner.ps1").read_text(encoding="utf-8")

    assert "required_github_runner_labels" in script
    assert "github_runner_labels_verified_locally = $false" in script
    assert "manifest_hashes_verified = $false" in script
    assert "does not verify GitHub labels, model/executable SHA256" in script
    assert "local_preflight_ready_github_labels_still_require_confirmation" in script
