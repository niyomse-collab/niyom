"""Keep V2.1.1 build and frozen imports isolated from legacy V1/V2 paths."""
import json
from pathlib import Path
import re

import pytest

from tools.v211_build_workspace_guard import (
    BuildWorkspaceError,
    validate_v211_build_workspace,
)


def test_legacy_model_download_runs_before_v211_only_cache_reuse():
    script = (Path(__file__).resolve().parents[1] / "build_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert r"$experimentalV211Pattern = '\A2\.1\.1(?:-beta\.[0-9]+)?\z'" in script
    assert '$experimentalV211 = ($Channel -eq "v2" -and $Version -match $experimentalV211Pattern)' in script

    legacy_start = script.index("if (-not $experimentalV211)")
    reuse_start = script.index("if (Test-Path -LiteralPath $Path)", legacy_start)
    legacy_branch = script[legacy_start:reuse_start]

    # V1 and stable V2 retain the original overwrite-and-hash-check behavior.
    assert "Invoke-WebRequest -Uri $Url -OutFile $Path" in legacy_branch
    assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in legacy_branch
    assert "Reusing existing verified" not in legacy_branch
    assert "$temporaryPath" not in legacy_branch
    assert "Remove-Item -LiteralPath $Path" not in legacy_branch

    # Verified cache reuse and atomic retries are V2.1.1-only.
    assert "Reusing existing verified" in script[reuse_start:]
    assert "V2.1.1 only: retry transient gateway/network failures" in script[reuse_start:]


def test_v211_workspace_guard_is_scoped_and_v2_still_protects_v1():
    script = (Path(__file__).resolve().parents[1] / "build_windows.ps1").read_text(
        encoding="utf-8"
    )
    selector = script.index("$experimentalV211Pattern =")
    v1_protection = script.index("# Never clean or replace files from a previously built/approved V1 checkout.")
    workspace_protection = script.index("# The shared script removes build/, dist/ and release/.")

    # All V2 builds still refuse to clean a workspace containing V1 artifacts.
    assert selector < v1_protection < workspace_protection
    assert script.index('if ($Channel -eq "v2")', v1_protection) < workspace_protection

    # The destructive workspace replacement guard applies only to V2.1.1.
    assert script.index("if ($experimentalV211)", workspace_protection) > workspace_protection


def test_frozen_v211_imports_are_excluded_from_v1_and_stable_v2():
    spec = (Path(__file__).resolve().parents[1] / "NiyomsilV2ArmCore.spec").read_text(
        encoding="utf-8"
    )
    assert 'build_info_path.read_text(encoding="utf-8-sig")' in spec
    pattern = r"2\.1\.1(?:-beta\.\d+)?"
    assert pattern in spec
    assert re.fullmatch(pattern, "2.1.1")
    assert re.fullmatch(pattern, "2.1.1-beta.653")
    assert not re.fullmatch(pattern, "2.1.10")

    conditional = spec.index("if IS_V211_BUILD:")
    fallback = spec.index("else:", conditional)
    v211_block = spec[conditional:fallback]
    legacy_block = spec[fallback:]
    assert "signprint_ai.v211_four_engine_bridge" in v211_block
    assert "tools.v211_four_engine_fusion" in v211_block
    assert "discover_package_modules" in v211_block
    assert "collect_submodules" in legacy_block
    assert "signprint_ai.v211_four_engine_bridge" not in legacy_block



def _seed_verified_v211_workspace(root: Path, version: str) -> None:
    source_commit = "a" * 40
    (root / "build").mkdir()
    app_dir = root / "dist" / "NiyomsilAIEnhancer"
    app_dir.mkdir(parents=True)
    release_dir = root / "release"
    release_dir.mkdir()
    (release_dir / "NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe").write_bytes(
        b"synthetic installer placeholder"
    )
    (root / "build_info.json").write_text(
        json.dumps(
            {
                "channel": "v2",
                "version": version,
                "source_commit": source_commit,
            }
        ),
        encoding="utf-8",
    )
    (app_dir / "BUILD_PROOF.txt").write_text(
        "\n".join(
            [
                "NIYOMSIL DESIGN v2 - VERIFIED INSTALLER BUILD PROOF",
                f"Version: {version}",
                f"Source commit: {source_commit}",
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("version", ["2.1.1", "2.1.1-beta.715"])
def test_v211_workspace_guard_reuses_verified_stable_and_beta_candidates(
    tmp_path: Path, version: str
):
    _seed_verified_v211_workspace(tmp_path, version)

    report = validate_v211_build_workspace(tmp_path, version)

    assert report["status"] == "verified_previous_v211_candidate"
    assert report["requested_version"] == version
    assert report["previous_version"] == version
    assert report["stable_v2_files_preserved"] is True
    assert report["v1_files_preserved"] is True


def test_workspace_guard_still_refuses_accepted_stable_v2_outputs(tmp_path: Path):
    (tmp_path / "build").mkdir()

    with pytest.raises(BuildWorkspaceError):
        validate_v211_build_workspace(tmp_path, "2.0.0")


def test_workspace_guard_does_not_treat_other_versions_as_v211(tmp_path: Path):
    _seed_verified_v211_workspace(tmp_path, "2.1.1")

    with pytest.raises(BuildWorkspaceError):
        validate_v211_build_workspace(tmp_path, "2.1.10")
