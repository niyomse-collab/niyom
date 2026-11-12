"""Keep V2.1.1 build hardening isolated from legacy V1/V2 model downloads."""
from pathlib import Path


def test_legacy_model_download_runs_before_v211_only_cache_reuse():
    script = (Path(__file__).resolve().parents[1] / "build_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert '$experimentalV211 = ($Channel -eq "v2" -and $Version -like "2.1.1*")' in script

    legacy_start = script.index("if (-not $experimentalV211)")
    reuse_start = script.index("if (Test-Path -LiteralPath $Path)", legacy_start)
    legacy_branch = script[legacy_start:reuse_start]

    # V1 and stable V2 retain the original overwrite-and-hash-check behavior.
    assert "Invoke-WebRequest -Uri $Url -OutFile $Path" in legacy_branch
    assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in legacy_branch
    assert "Reusing existing verified" not in legacy_branch
    assert "$temporaryPath" not in legacy_branch
    assert "Remove-Item -LiteralPath $Path" not in legacy_branch

    # Safe reuse and atomic retry remain confined to the experimental branch.
    assert "Reusing existing verified" in script[reuse_start:]
    assert "V2.1.1 only: retry transient gateway/network failures" in script[reuse_start:]
