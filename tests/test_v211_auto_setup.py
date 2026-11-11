"""Four-AI installer-time provisioning tests: no internet or real executable runs."""
from pathlib import Path

import pytest

from signprint_ai import v211_auto_setup as setup
from tools import v211_official_assets_audit as official
from tools import v211_provision_four_engines as provisioning
from tools import v211_real_engine_manifest as manifests


def test_one_time_provision_checks_four_without_shipping_models(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    saved = []
    packages = {name: {"url": "https://example.org/test-only"}
                for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")}
    monkeypatch.setattr(official, "PACKAGES", packages)

    def simulated_verified_archive(dest, package):
        saved.append(Path(dest).name)
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"synthetic ZIP placeholder; never run")
        return {"status": "downloaded_verified"}

    def fake_provision(archives, folder, manifest):
        assert sorted(saved) == sorted(name + ".zip" for name in packages)
        assert archives.is_dir()
        folder.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text('{"four_models":"test"}', encoding="utf-8")
        return {"research_only": True}

    monkeypatch.setattr(provisioning, "ensure_verified_archive", simulated_verified_archive)
    monkeypatch.setattr(provisioning, "provision_from_archives", fake_provision)
    monkeypatch.setattr(manifests, "load_real_engine_manifest", lambda path:
                        {name: "model stub" for name in packages})
    report = setup.provision_after_consent()
    assert report["status"] == "installed_for_offline_qa"
    assert report["manifest_source"] == "localappdata_default"
    assert set(report["verified_engine_names"]) == set(packages)
    assert report["real_inference_verified_on_this_pc"] is False
    assert report["quality_certified"] is False
    assert setup.default_manifest().exists()


def test_explicit_manifest_override_is_the_path_provisioned_and_later_checked(
    tmp_path, monkeypatch
):
    local_appdata = tmp_path / "local-appdata"
    override = tmp_path / "portable-config" / "manifest.json"
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(override))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    packages = {name: {"url": "https://example.org/test-only"}
                for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")}
    monkeypatch.setattr(official, "PACKAGES", packages)
    monkeypatch.setattr(provisioning, "ensure_verified_archive",
                        lambda dest, package: Path(dest).write_bytes(b"synthetic"))
    provisioned = {}

    def fake_provision(archives, folder, manifest):
        provisioned["manifest"] = Path(manifest)
        provisioned["install_dir"] = Path(folder)
        Path(manifest).parent.mkdir(parents=True, exist_ok=True)
        Path(manifest).write_text('{"four_models":"test"}', encoding="utf-8")
        return {"research_only": True}

    monkeypatch.setattr(provisioning, "provision_from_archives", fake_provision)
    monkeypatch.setattr(manifests, "load_real_engine_manifest", lambda path:
                        {name: "model stub" for name in packages})

    report = setup.provision_after_consent()

    assert provisioned["manifest"] == override.resolve()
    assert provisioned["install_dir"] == setup.qa_root() / "engines"
    assert report["manifest"] == str(override.resolve())
    assert report["manifest_source"] == "explicit_override"
    assert override.is_file()
    assert not setup.default_manifest().exists()
    assert set(manifests.load_real_engine_manifest(override)) == set(packages)


def test_setup_fails_closed_if_any_native_engine_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    setup.default_manifest().parent.mkdir(parents=True)
    setup.default_manifest().write_text("{}")
    monkeypatch.setattr(manifests, "load_real_engine_manifest", lambda path:
                        (_ for _ in ()).throw(ValueError("missing AI model")))
    with pytest.raises(ValueError, match="missing AI model"):
        setup.provision_after_consent()


def test_editor_never_prompts_or_downloads_on_first_launch():
    app_source = (Path(__file__).resolve().parents[1] /
                  "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    assert "_offer_v211_four_ai_setup" not in app_source
    assert "needs_initial_setup" not in app_source
    assert "install_for_offline_use()" not in app_source
    assert "provision_after_consent" not in app_source
    assert "four_ai_setup_done" not in app_source
    assert "four_ai_setup_failed" not in app_source
