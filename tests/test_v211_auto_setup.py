"""Four-AI first-run setup tests: no internet, no real executable runs."""
from pathlib import Path

import pytest

from signprint_ai import v211_auto_setup as setup
from tools import v211_official_assets_audit as official
from tools import v211_provision_four_engines as provisioning
from tools import v211_real_engine_manifest as manifests


def test_first_run_setup_required_until_manifest_is_verified(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    assert setup.needs_initial_setup() is True

    setup.default_manifest().parent.mkdir(parents=True)
    setup.default_manifest().write_text("placeholder, not a verified manifest", encoding="utf-8")
    assert setup.needs_initial_setup() is True

    monkeypatch.setattr(
        manifests,
        "load_real_engine_manifest",
        lambda path: {
            name: object()
            for name in ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
        },
    )
    assert setup.needs_initial_setup() is False


def test_explicit_manifest_override_must_also_verify_all_four(tmp_path, monkeypatch):
    override = tmp_path / "external-manifest.json"
    override.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(override))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    assert setup.needs_initial_setup() is True

    monkeypatch.setattr(
        manifests,
        "load_real_engine_manifest",
        lambda path: {"real_esrgan": object(), "waifu2x": object()},
    )
    assert setup.needs_initial_setup() is True


def test_explicit_disable_prevents_setup_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "0")
    assert not setup.needs_initial_setup()


def test_one_time_provision_checks_four_without_shipping_models(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    saved = []
    setup.record_consent_declined()
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
    assert not setup.declined_marker_path().exists()


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
    assert setup.needs_initial_setup() is False


def test_setup_fails_closed_if_any_native_engine_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    setup.default_manifest().parent.mkdir(parents=True)
    setup.default_manifest().write_text("{}")
    monkeypatch.setattr(manifests, "load_real_engine_manifest", lambda path:
                        (_ for _ in ()).throw(ValueError("missing AI model")))
    with pytest.raises(ValueError, match="missing AI model"):
        setup.provision_after_consent()


def test_declined_first_run_offer_is_not_repeated_until_user_reconsents(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    assert setup.needs_initial_setup() is True
    marker = setup.record_consent_declined()
    assert marker.is_file()
    assert setup.needs_initial_setup() is False

    # An explicit later installer/app consent attempt clears the decline.
    setup.clear_consent_declined()
    assert setup.needs_initial_setup() is True


def test_editor_offers_one_consent_for_all_four_without_direct_download_code():
    app_source = (Path(__file__).resolve().parents[1] /
                  "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    assert "self.after(500, self._offer_v211_four_ai_setup)" in app_source
    assert "messagebox.askyesno(" in app_source
    assert "default=messagebox.NO" in app_source
    assert "record_consent_declined()" in app_source
    assert "install_for_offline_use()" in app_source
    assert "four_ai_setup_done" in app_source
    assert "four_ai_setup_failed" in app_source
    # Downloads remain behind the consented setup service, not app startup code.
    assert "provision_after_consent" not in app_source
