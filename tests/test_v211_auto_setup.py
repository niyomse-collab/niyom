"""Four-AI consent/provisioning tests: no internet or real executable runs."""
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


def test_editor_offers_one_first_launch_consent_and_downloads_only_after_yes():
    app_source = (Path(__file__).resolve().parents[1] /
                  "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    assert "self.after(600, self._offer_v211_four_ai_setup)" in app_source
    assert "messagebox.askyesno(" in app_source
    assert "record_setup_declined()" in app_source
    assert "provision_after_user_consent(consent=True)" in app_source
    assert "four_ai_setup_done" in app_source
    assert "four_ai_setup_failed" in app_source
    assert app_source.index("accepted = messagebox.askyesno(") < app_source.index(
        "self._start_v211_four_ai_setup()"
    )


def test_initial_setup_state_is_local_and_requires_consent_when_models_are_absent(
    tmp_path, monkeypatch
):
    local_appdata = tmp_path / "AppData" / "Local"
    local_appdata.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)

    report = setup.initial_setup_state()

    assert report == {"status": "needs_consent"}
    assert not setup.qa_root().exists()


def test_decline_marker_suppresses_repeated_first_launch_prompt(tmp_path, monkeypatch):
    local_appdata = tmp_path / "AppData" / "Local"
    local_appdata.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)

    report = setup.record_setup_declined()

    assert report["status"] == "declined"
    assert setup.initial_setup_state()["status"] == "declined"
    assert (setup.qa_root() / "setup-declined.flag").is_file()


def test_initial_setup_state_rejects_an_unverifiable_existing_manifest(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    manifest = setup.default_manifest()
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(manifests, "load_real_engine_manifest", lambda _path:
                        (_ for _ in ()).throw(ValueError("invalid manifest")))

    assert setup.initial_setup_state()["status"] == "invalid_existing_manifest"


def test_public_setup_entry_refuses_to_provision_without_affirmative_consent(monkeypatch):
    from signprint_ai import v211_setup_cli

    called = []
    monkeypatch.setattr(v211_setup_cli, "_run_and_publish_success", lambda: called.append(True))
    with pytest.raises(PermissionError, match="affirmative"):
        v211_setup_cli.provision_after_user_consent(consent=False)
    assert called == []

    v211_setup_cli.provision_after_user_consent(consent=True)
    assert called == [True]

def _create_manifest_symlink_or_skip(link: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("external manifest target", encoding="utf-8")
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("this runner cannot create file symlinks: " + str(exc))


def test_selected_manifest_preserves_symlink_for_fail_closed_validation(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    override = tmp_path / "portable" / "manifest.json"
    target = tmp_path / "outside" / "manifest.json"
    _create_manifest_symlink_or_skip(override, target)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(override))

    selected = setup.selected_manifest()

    assert selected == Path(str(override.absolute()))
    assert selected.is_symlink()
    assert setup.initial_setup_state()["status"] == "invalid_existing_manifest"


def test_consent_provisioning_rejects_manifest_symlink_before_any_download(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    override = tmp_path / "portable" / "manifest.json"
    target = tmp_path / "outside" / "manifest.json"
    _create_manifest_symlink_or_skip(override, target)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", str(override))

    downloaded = []
    monkeypatch.setattr(provisioning, "ensure_verified_archive",
                        lambda *args, **kwargs: downloaded.append(args))
    monkeypatch.setattr(manifests, "load_real_engine_manifest",
                        lambda _path: (_ for _ in ()).throw(AssertionError(
                            "symlink target must not be read"
                        )))

    with pytest.raises(RuntimeError, match="manifest path is not a safe regular file"):
        setup.provision_after_consent()

    assert downloaded == []

