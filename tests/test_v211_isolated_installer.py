"""Prevent a V2.1.1 experiment from overwriting the accepted V2 installer."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _setting(text: str, name: str) -> str:
    match = re.search(r"(?m)^" + re.escape(name) + r"=(.+)$", text)
    assert match, name + " missing"
    return match.group(1).strip()


def test_experimental_app_id_and_install_folder_differ_from_stable_v2():
    v2 = (ROOT / "installer_v2.iss").read_text(encoding="utf-8")
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    assert _setting(qa, "AppId") != _setting(v2, "AppId")
    assert _setting(qa, "DefaultDirName") != _setting(v2, "DefaultDirName")
    assert _setting(qa, "OutputBaseFilename") != _setting(v2, "OutputBaseFilename")
    assert _setting(qa, "AppName") == "{#MyAppName}"
    assert "EXPERIMENTAL" in qa
    assert "DisableDirPage=yes" in qa
    assert "UsePreviousAppDir=no" in qa
    assert "NiyomSilpDesignV2" in qa
    assert "InstalledV2" in qa
    assert "V2 Stable" in qa


def test_v211_build_dispatch_and_workflow_only_publish_unique_installer():
    ps = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" /
                "v211-four-engine-bridge-windows.yml").read_text(encoding="utf-8")
    assert '$Version -like "2.1.1*"' in ps
    assert 'installer_v211_experimental.iss' in ps
    assert 'NiyomSilp-Design-v211-EXPERIMENTAL-Setup' in ps
    assert 'release/NiyomSilp-Design-v211-EXPERIMENTAL-Setup*' in workflow
    assert 'release/NiyomSilp-Design-v2-Setup*' not in workflow


def test_four_engine_download_requires_affirmative_consent():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    app = (ROOT / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    tasks = qa.split("[Tasks]", 1)[1].split("[Run]", 1)[0]
    run_section = qa.split("[Run]", 1)[1].split("[Code]", 1)[0]
    provision_line = next(line for line in run_section.splitlines()
                          if "GetProvisionParameters" in line)
    task_line = next(line for line in tasks.splitlines()
                     if 'Name: "installfourai"' in line)
    assert "I agree:" in task_line
    assert "Flags: unchecked" in task_line
    assert "checkedonce" not in task_line
    assert "GetProvisionParameters" in provision_line
    assert "waituntilterminated" in provision_line
    assert "skipifsilent" not in provision_line
    assert "Check: ShouldLaunchEditor" in run_section
    assert "GetCustomSetupExitCode" in qa
    assert "CurStepChanged" in qa
    assert "setup-complete.flag" in qa
    assert "setup-pending.flag" in qa
    marker_block = qa.split("procedure CurStepChanged", 1)[1].split(
        "function GetCustomSetupExitCode", 1
    )[0]
    assert "CurStep = ssInstall" in marker_block
    assert "CurStep = ssDone" in marker_block
    assert "CurStep = ssPostInstall" not in marker_block
    assert marker_block.index("CurStep = ssInstall") < marker_block.index(
        "CurStep = ssDone"
    )
    assert "ssDone is reached after the [Run] entries have completed" in qa
    assert "ForceDirectories(ExtractFileDir(FourAIPendingMarker()))" in marker_block
    assert marker_block.index("ForceDirectories(") < marker_block.index(
        "SaveStringToFile(FourAIPendingMarker()"
    )
    assert "FourAISetupArmed" in qa
    # The installer is the only consent surface. If its task is skipped,
    # the editor opens directly in accepted V2 mode and never prompts later.
    assert "self.after(500, self._offer_v211_four_ai_setup)" not in app
    assert "_offer_v211_four_ai_setup" not in app
    assert "needs_initial_setup" not in app
    assert "install_for_offline_use()" not in app
    assert "provision_after_consent" not in app
    assert "four_ai_setup_done" not in app
    assert "four_ai_setup_failed" not in app


def test_installer_silent_mode_is_noninteractive_but_still_provisions():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    cli = (ROOT / "signprint_ai" / "v211_setup_cli.py").read_text(encoding="utf-8")
    assert "if WizardSilent then" in qa
    assert " --silent" in qa
    assert "def main(*, silent: bool = False, preflight_only: bool = False)" in cli
    assert "if silent:" in cli
    assert "installer-setup.log" in cli


def test_frozen_spec_installs_basicsr_compat_before_static_package_discovery():
    spec = (ROOT / "NiyomsilV2ArmCore.spec").read_text(encoding="utf-8")
    alias = '"torchvision.transforms.functional_tensor"'
    registration = "sys.modules[_compat_name] = _compat_module"
    discovery_import = (
        "from tools.v211_frozen_imports import discover_package_modules"
    )

    assert "from torchvision.transforms.functional import rgb_to_grayscale" in spec
    assert alias in spec
    assert registration in spec
    # The analysis-process alias must exist before our static filesystem scan
    # imports the package-discovery helper. PyInstaller's collect_submodules()
    # uses an isolated interpreter and is deliberately not used in this spec.
    assert spec.index(registration) < spec.index(discovery_import)
    assert "discover_package_modules(Path(package_spec.origin).parent, package)" in spec
    assert '"tools.v211_four_engine_tiled_inference"' in spec
    assert "collect_submodules(" not in spec
    assert 'runtime_hooks=[str(ROOT / "pyi_rth_basicsr_compat.py")]' in spec


def test_frozen_import_smoke_exercises_disk_backed_libvips_region_reader():
    run = (ROOT / "run.py").read_text(encoding="utf-8")
    smoke = run.split('if os.environ.get("NIYOMSIL_IMPORT_SMOKE") == "1":', 1)[1]
    assert "pyvips.Image.new_from_file(" in smoke
    assert 'access="random"' in smoke
    assert "pyvips.Region.new(disk_image)" in smoke
    assert "region.fetch(3, 4, 5, 6)" in smoke
    assert "bytes(pixels[:3]) == bytes((17, 31, 47))" in smoke
    assert "del region, disk_image" in smoke


def test_frozen_candidate_checks_the_actual_provisioning_dispatch_without_network():
    workflow = (ROOT / ".github" / "workflows" /
                "v211-four-engine-bridge-windows.yml").read_text(encoding="utf-8")
    run = (ROOT / "run.py").read_text(encoding="utf-8")
    cli = (ROOT / "signprint_ai" / "v211_setup_cli.py").read_text(encoding="utf-8")

    assert "Verify packaged four-engine provisioning dispatch without downloads" in workflow
    assert "'--provision-v211-four-ai', '--check-only'" in workflow
    assert '["--provision-v211-four-ai", "--check-only"]' in run
    assert "preflight_only=\"--check-only\" in sys.argv[1:]" in run
    assert "def preflight_v211_provisioning()" in cli
    assert "preflight_v211_provisioning()" in cli

def test_uninstall_model_cache_removal_requires_interactive_consent_and_safe_cli():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    run = (ROOT / "run.py").read_text(encoding="utf-8")
    cli = (ROOT / "signprint_ai" / "v211_setup_cli.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" /
                "v211-four-engine-bridge-windows.yml").read_text(encoding="utf-8")

    registry = qa.split("[Registry]", 1)[1].split("[Icons]", 1)[0]
    code = qa.split("[Code]", 1)[1]
    uninstall_event = code.split(
        "procedure CurUninstallStepChanged", 1
    )[1]

    assert 'ValueName: "FourAIDataRoot"' in registry
    assert 'ValueData: "{localappdata}\\NiyomSilp\\V211-FourAI-QA"' in registry
    assert "Flags: uninsdeletevalue" in registry
    assert "function InitializeUninstall(): Boolean;" in code
    assert "CurUninstallStep = usUninstall" in uninstall_event
    assert "not UninstallSilent" in uninstall_event
    assert "CurrentUserFourAIDataRoot :=" in uninstall_event
    assert "ExpandConstant('{localappdata}\\NiyomSilp\\V211-FourAI-QA')" in uninstall_event
    assert "Uppercase(FourAIDataRootPath) <> Uppercase(CurrentUserFourAIDataRoot)" in uninstall_event
    assert "It was left untouched for safety." in uninstall_event
    assert "MB_YESNO or MB_DEFBUTTON2" in uninstall_event
    assert "IDYES" in uninstall_event
    assert "SW_HIDE" in uninstall_event
    assert "ewWaitUntilTerminated" in uninstall_event
    assert "--remove-v211-four-ai-assets --confirmed-by-user --data-root" in uninstall_event
    assert "[UninstallRun]" not in qa

    assert '"--remove-v211-four-ai-assets"' in run
    assert '"--confirmed-by-user"' in run
    assert '"--data-root"' in run
    assert "cleanup_four_engine_assets(sys.argv[4], confirmed=True)" in run
    assert "def cleanup_four_engine_assets(" in cli
    assert "_validate_four_ai_data_root(data_root)" in cli
    assert "_remove_cache_entry_without_following_links" in cli
    assert "os.path.ismount(path)" in cli
    assert "os.path.ismount(candidate)" in cli
    assert "os.path.ismount(root)" in cli
    assert "Verify packaged consented model-cache cleanup on isolated synthetic data" in workflow
    assert "'--remove-v211-four-ai-assets', '--confirmed-by-user', '--data-root'" in workflow



def test_experimental_installer_is_per_user_for_profile_local_model_cache():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    setup = qa.split("[Setup]", 1)[1].split("[Files]", 1)[0]
    registry = qa.split("[Registry]", 1)[1].split("[Icons]", 1)[0]
    code = qa.split("[Code]", 1)[1]
    initialize_uninstall = code.split(
        "function InitializeUninstall(): Boolean;", 1
    )[1].split("procedure CurUninstallStepChanged", 1)[0]

    # Four-engine models, setup markers and uninstall cleanup are per-user.
    # Inno's lowest mode keeps {localappdata}, {autopf}, and the auto shell
    # folders in the same profile instead of switching to an admin account.
    assert "PrivilegesRequired=lowest" in setup
    assert "DefaultDirName={autopf}\\NiyomSilpDesignV211Experimental" in setup
    assert 'Root: HKCU64; Subkey: "Software\\NiyomSilp\\V211Experimental"' in registry
    assert "Root: HKLM64; Subkey: \"Software\\NiyomSilp\\V211Experimental\"" not in registry
    assert "HKCU64," in initialize_uninstall
    assert "HKLM64," not in initialize_uninstall


def test_manual_gpu_diagnostic_resolves_the_per_user_installer_path():
    doc = (ROOT / "docs" / "V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md").read_text(
        encoding="utf-8"
    )
    installer = (ROOT / "installer_v211_experimental.iss").read_text(
        encoding="utf-8"
    )
    assert "PrivilegesRequired=lowest" in installer
    assert "DefaultDirName={autopf}\\NiyomSilpDesignV211Experimental" in installer
    assert "RegistryView]::Registry64" in doc
    assert "Inno Setup: App Path" in doc
    assert "--diagnose-v211-four-ai" in doc
    assert "$env:ProgramFiles\\NiyomSilpDesignV211Experimental" not in doc
    assert "2,048 MiB" in doc


def _write_v211_candidate_workspace(root: Path, version="2.1.1-beta.469", commit="a" * 40):
    import json

    (root / "build").mkdir(parents=True, exist_ok=True)
    app = root / "dist" / "NiyomsilAIEnhancer"
    app.mkdir(parents=True, exist_ok=True)
    release = root / "release"
    release.mkdir(parents=True, exist_ok=True)
    (root / "build_info.json").write_text(json.dumps({
        "channel": "v2", "version": version, "source_commit": commit,
    }), encoding="utf-8")
    (app / "BUILD_PROOF.txt").write_text(
        "NIYOMSIL DESIGN v2 - VERIFIED INSTALLER BUILD PROOF\n"
        f"Version: {version}\n"
        f"Source commit: {commit}\n",
        encoding="utf-8",
    )
    (release / "NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe").write_bytes(b"candidate")
    (release / "SHA256SUMS.txt").write_text("candidate hashes only", encoding="ascii")


def test_v211_build_workspace_guard_allows_a_clean_checkout_and_same_candidate_family(tmp_path):
    from tools.v211_build_workspace_guard import validate_v211_build_workspace

    assert validate_v211_build_workspace(
        tmp_path, "2.1.1-beta.470"
    )["status"] == "clean_workspace"

    _write_v211_candidate_workspace(tmp_path)
    report = validate_v211_build_workspace(tmp_path, "2.1.1-beta.470")
    assert report["status"] == "verified_previous_v211_candidate"
    assert report["stable_v2_files_preserved"] is True
    assert report["v1_files_preserved"] is True


def test_v211_build_workspace_guard_refuses_accepted_v2_stable_outputs(tmp_path):
    import json
    import pytest
    from tools.v211_build_workspace_guard import (
        BuildWorkspaceError, validate_v211_build_workspace,
    )

    (tmp_path / "build_info.json").write_text(json.dumps({
        "channel": "v2", "version": "2.0.0-beta.1", "source_commit": "b" * 40,
    }), encoding="utf-8")
    release = tmp_path / "release"
    release.mkdir()
    stable = release / "NiyomSilp-Design-v2-Setup.exe"
    stable.write_bytes(b"accepted-v2-installer")

    with pytest.raises(BuildWorkspaceError, match="accepted V2 stable"):
        validate_v211_build_workspace(tmp_path, "2.1.1-beta.470")
    assert stable.read_bytes() == b"accepted-v2-installer"


def test_v211_build_workspace_guard_refuses_partial_or_unverifiable_outputs(tmp_path):
    import pytest
    from tools.v211_build_workspace_guard import (
        BuildWorkspaceError, validate_v211_build_workspace,
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    sentinel = dist / "stable-output-do-not-delete.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(BuildWorkspaceError, match="dist/ contains files outside"):
        validate_v211_build_workspace(tmp_path, "2.1.1-beta.470")
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_v211_build_workspace_guard_refuses_mismatched_proof_and_unknown_release_files(tmp_path):
    import pytest
    from tools.v211_build_workspace_guard import (
        BuildWorkspaceError, validate_v211_build_workspace,
    )

    _write_v211_candidate_workspace(tmp_path)
    proof = tmp_path / "dist" / "NiyomsilAIEnhancer" / "BUILD_PROOF.txt"
    proof.write_text(
        "NIYOMSIL DESIGN v2 - VERIFIED INSTALLER BUILD PROOF\n"
        "Version: 2.1.1-beta.468\n"
        f"Source commit: {'a' * 40}\n",
        encoding="utf-8",
    )
    with pytest.raises(BuildWorkspaceError, match="matching V2.1.1 BUILD_PROOF"):
        validate_v211_build_workspace(tmp_path, "2.1.1-beta.470")

    _write_v211_candidate_workspace(tmp_path)
    unknown = tmp_path / "release" / "customer-artwork.png"
    unknown.write_bytes(b"never delete")
    with pytest.raises(BuildWorkspaceError, match="unverified file"):
        validate_v211_build_workspace(tmp_path, "2.1.1-beta.470")
    assert unknown.read_bytes() == b"never delete"


def test_v2_build_script_guards_workspace_before_cleanup_and_reuses_verified_models():
    ps = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
    guard = ps.index("v211_build_workspace_guard.py")
    venv = ps.index("& $python -m venv .venv-build")
    cleanup = ps.index("Remove-Item build, dist, release")
    assert guard < venv < cleanup
    assert "function Ensure-VerifiedDownload" in ps
    assert "Existing $Label SHA256 differs from the pinned model; refusing to overwrite" in ps
    assert "Reusing existing verified " + chr(36) + "{Label}" in ps
    assert ps.count("Invoke-WebRequest -Uri $Url -OutFile $Path") == 1
    assert "Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath" not in ps
    assert "Invoke-WebRequest -Uri $gfpganUrl -OutFile $gfpganPath" not in ps
    assert "Invoke-WebRequest -Uri $retinaUrl -OutFile $retinaPath" not in ps
    assert ps.index("Normalize the legacy V2 default") < guard



def test_v211_verified_download_retries_only_transient_errors_and_publishes_atomically():
    ps = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
    assert "if (-not $experimentalV211)" in ps
    assert "$maxAttempts = 5" in ps
    assert "Invoke-WebRequest -Uri $Url -OutFile $temporaryPath -TimeoutSec 90" in ps
    assert "$statusCode -in @(408, 425, 429, 500, 502, 503, 504)" in ps
    assert "[System.IO.File]::Move($temporaryPath, $Path)" in ps
    assert "Start-Sleep -Seconds $delaySeconds" in ps
    assert "Download retries exhausted for $Label." in ps
    # V1 and stable V2 keep their legacy direct-download path unchanged.
    assert ps.count("Invoke-WebRequest -Uri $Url -OutFile $Path") == 1


def test_cli_smoke_classifies_provisioning_block_without_fabricating_engine_reports():
    workflow = (ROOT / ".github" / "workflows" /
                "v211-four-engine-real-cli-smoke.yml").read_text(encoding="utf-8")
    assert "id: provision" in workflow
    assert "steps.provision.outcome == 'success'" in workflow
    assert "PROVISIONING_BLOCKED: official archives were not verified" in workflow
    assert "native inference was not attempted" in workflow
