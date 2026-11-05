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



def test_four_engine_setup_runs_during_install_not_when_editor_opens():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    app = (ROOT / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    assert 'Name: "installfourai"' in qa
    assert "Flags: checkedonce" in qa
    assert 'Parameters: "--provision-v211-four-ai"' in qa
    assert "runascurrentuser" in qa
    assert "waituntilterminated" in qa
    assert "_offer_v211_four_ai_setup" not in app
    assert "provision_after_consent" not in app


def test_installer_provision_window_is_not_hidden():
    qa = (ROOT / "installer_v211_experimental.iss").read_text(encoding="utf-8")
    assert "Parameters: \"--provision-v211-four-ai\"" in qa
    assert "Flags: waituntilterminated runascurrentuser skipifsilent" in qa
    assert "runhidden" not in qa
