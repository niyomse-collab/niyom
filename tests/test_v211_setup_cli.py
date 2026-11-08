"""Installer-time four-engine setup command tests; no network or real model runs."""
from pathlib import Path

import pytest

from signprint_ai import v211_auto_setup
from signprint_ai import v211_setup_cli


def test_installer_setup_accepts_exactly_four_verified_engines(monkeypatch):
    expected = {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "installed_for_offline_qa",
            "verified_engine_names": sorted(expected),
            "quality_certified": False,
        },
    )
    result = v211_setup_cli.install_for_offline_use()
    assert set(result["verified_engine_names"]) == expected
    assert result["quality_certified"] is False


def test_installer_setup_rejects_partial_or_unverified_engine_set(monkeypatch):
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "installed_for_offline_qa",
            "verified_engine_names": ["real_esrgan", "waifu2x", "real_cugan"],
        },
    )
    with pytest.raises(RuntimeError, match="exactly the required engines"):
        v211_setup_cli.install_for_offline_use()


def test_installer_setup_rejects_unknown_terminal_status(monkeypatch):
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "failed",
            "verified_engine_names": [
                "real_esrgan", "waifu2x", "real_cugan", "anime4k"
            ],
        },
    )
    with pytest.raises(RuntimeError, match="completed state"):
        v211_setup_cli.install_for_offline_use()


def test_command_is_dispatched_before_editor_import():
    root = Path(__file__).resolve().parents[1]
    source = (root / "run.py").read_text(encoding="utf-8")
    assert source.index("--provision-v211-four-ai") < source.index(
        "from signprint_ai.app_v2 import main"
    )
    assert "signprint_ai.v211_setup_cli" in source
    assert '"--check-only"' in source


def test_provision_preflight_validates_exact_upstream_versions_and_digest_sources(monkeypatch):
    from tools import v211_official_assets_audit as audit

    result = v211_setup_cli.preflight_v211_provisioning()
    assert set(result["engines"]) == {
        "real_esrgan", "waifu2x", "real_cugan", "anime4k"
    }
    assert result["release_pins"] == {
        "real_esrgan": "v0.2.5.0",
        "waifu2x": "20250915",
        "real_cugan": "20220728",
        "anime4k": "v3.2.0",
    }
    assert result["digest_sources"] == {
        "real_esrgan": "observed_sha256",
        "waifu2x": "release_sha256",
        "real_cugan": "observed_sha256",
        "anime4k": "release_sha256",
    }
    assert result["license_sources"]["anime4k"] == (
        "https://github.com/TianZerL/Anime4KCPP/blob/master/LICENSE-GPLv3"
    )
    assert result["network_started"] is False
    assert result["filesystem_modified"] is False

    monkeypatch.setitem(audit.PACKAGES["anime4k"], "release_sha256", "not-a-sha256")
    with pytest.raises(RuntimeError, match="SHA256 pin"):
        v211_setup_cli.preflight_v211_provisioning()


def test_check_only_main_does_not_clear_markers_or_start_setup(monkeypatch):
    def forbidden():
        pytest.fail("check-only must not touch installer markers")

    monkeypatch.setattr(v211_setup_cli, "_clear_completion_marker", forbidden)
    monkeypatch.setattr(v211_setup_cli, "preflight_v211_provisioning", lambda: {"ok": True})
    assert v211_setup_cli.main(preflight_only=True) == 0


def test_silent_setup_publishes_marker_only_after_all_four_verify(monkeypatch, tmp_path):
    expected = {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
    marker = tmp_path / "setup-complete.flag"
    pending = tmp_path / "setup-pending.flag"
    pending.write_text("pending", encoding="utf-8")
    monkeypatch.setattr(v211_setup_cli, "completion_marker_path", lambda: marker)
    monkeypatch.setattr(v211_setup_cli, "pending_marker_path", lambda: pending)
    monkeypatch.setattr(
        v211_setup_cli,
        "install_for_offline_use",
        lambda: {
            "status": "installed_for_offline_qa",
            "verified_engine_names": sorted(expected),
        },
    )
    assert v211_setup_cli.main(silent=True) == 0
    assert marker.read_text(encoding="utf-8").startswith("NiyomSilp V2.1.1")
    assert not pending.exists()


def test_silent_setup_failure_removes_stale_marker_and_keeps_pending_gate(
    monkeypatch, tmp_path
):
    marker = tmp_path / "setup-complete.flag"
    pending = tmp_path / "setup-pending.flag"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("stale success", encoding="utf-8")
    pending.write_text("pending", encoding="utf-8")
    monkeypatch.setattr(v211_setup_cli, "completion_marker_path", lambda: marker)
    monkeypatch.setattr(v211_setup_cli, "pending_marker_path", lambda: pending)

    private_detail = r"C:\Users\Customer\Artwork\secret-sign.png"

    def fail():
        raise RuntimeError("simulated model verification failure at " + private_detail)

    monkeypatch.setattr(v211_setup_cli, "install_for_offline_use", fail)
    assert v211_setup_cli.main(silent=True) == 1
    assert not marker.exists()
    assert pending.exists()
    log = marker.with_name("installer-setup.log").read_text(encoding="utf-8")
    assert "FAILED setup_failed" in log
    assert private_detail not in log
    assert "simulated model verification failure" not in log


def test_safe_failure_codes_never_include_exception_details():
    from pathlib import Path

    secret = r"C:\Users\Customer\Artwork\private.png"
    assert v211_setup_cli.safe_failure_code(FileNotFoundError(secret)) == "missing_asset"
    assert v211_setup_cli.safe_failure_code(PermissionError(secret)) == "permission_denied"
    assert v211_setup_cli.safe_failure_code(TimeoutError(secret)) == "network_timeout"
    assert v211_setup_cli.safe_failure_code(ValueError(secret)) == "verification_failed"
    assert v211_setup_cli.safe_failure_code(RuntimeError(secret)) == "setup_failed"


def test_setup_ui_worker_queues_only_safe_failure_code():
    source = (Path(__file__).resolve().parents[1] /
              "signprint_ai" / "v211_setup_cli.py").read_text(encoding="utf-8")
    assert 'events.put(("failure", safe_failure_code(exc)))' in source
    assert 'str(payload)' in source  # payload is the fixed safe code, not an Exception
    assert 'str(exc)' not in source


def test_setup_log_writer_allowlists_messages_and_engine_names(monkeypatch, tmp_path):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)
    secret = r"C:\Users\Customer\Artwork\private-sign.png"

    v211_setup_cli._record("FAILED " + secret)
    v211_setup_cli._record("FAILED setup_failed\\n" + secret)
    v211_setup_cli._record("SUCCESS verified engines: " + secret)
    v211_setup_cli._record(
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x"
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "FAILED setup_failed",
        "FAILED setup_failed",
        "FAILED setup_failed",
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x",
    ]
    assert secret not in log_path.read_text(encoding="utf-8")

@pytest.mark.parametrize(
    "payload",
    [
        "FAILED setup_failed\nSUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x",
        "FAILED setup_failed\r\nSUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x",
        "FAILED setup_failed\rSUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x",
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x\nSUCCESS verified engines: real_esrgan",
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x\r\nFAILED setup_failed",
        "FAILED setup_failed\u2028C:\\Users\\Customer\\Artwork\\secret.png",
        "FAILED setup_failed\x00C:\\Users\\Customer\\Artwork\\secret.png",
        "FAILED setup_failed\tC:\\Users\\Customer\\Artwork\\secret.png",
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x\nC:\\Users\\Customer\\Artwork\\secret.png",
    ],
)
def test_setup_log_writer_rejects_real_linebreaks_and_control_injection(
    monkeypatch, tmp_path, payload
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    v211_setup_cli._record(payload)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["FAILED setup_failed"]
    content = log_path.read_text(encoding="utf-8")
    assert "Customer" not in content
    assert "Artwork" not in content
    assert "secret.png" not in content


def test_setup_log_writer_canonicalizes_only_exact_success_engine_set(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    v211_setup_cli._record(
        "SUCCESS verified engines: waifu2x,real_esrgan,anime4k,real_cugan"
    )
    v211_setup_cli._record(
        "SUCCESS verified engines: waifu2x,real_esrgan,anime4k,real_cugan,waifu2x"
    )
    v211_setup_cli._record(
        "SUCCESS verified engines: waifu2x,real_esrgan,anime4k,real_cugan\rFAILED setup_failed"
    )

    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "SUCCESS verified engines: anime4k,real_cugan,real_esrgan,waifu2x",
        "FAILED setup_failed",
        "FAILED setup_failed",
    ]

def _four_ai_cache_root(tmp_path):
    return (tmp_path / "Profile" / "AppData" / "Local" /
            "NiyomSilp" / "V211-FourAI-QA")


def test_uninstall_cache_cleanup_requires_explicit_confirmation(tmp_path):
    root = _four_ai_cache_root(tmp_path)
    engine_file = root / "engines" / "real-esrgan" / "realesrgan-ncnn-vulkan.exe"
    engine_file.parent.mkdir(parents=True)
    engine_file.write_bytes(b"synthetic engine placeholder")

    result = v211_setup_cli.cleanup_four_engine_assets(root, confirmed=False)

    assert result == {"status": "consent_required", "removed": False}
    assert engine_file.is_file()


def test_uninstall_cache_cleanup_removes_only_owned_assets_and_keeps_unknown_files(
    tmp_path,
):
    root = _four_ai_cache_root(tmp_path)
    archive = root / "archives" / "real_esrgan.zip"
    engine = root / "engines" / "real-esrgan" / "model.bin"
    archive.parent.mkdir(parents=True)
    engine.parent.mkdir(parents=True)
    archive.write_bytes(b"synthetic archive placeholder")
    engine.write_bytes(b"synthetic model placeholder")
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "setup-complete.flag").write_text("verified", encoding="ascii")
    unknown = root / "operator-note.txt"
    unknown.write_text("keep this unrelated file", encoding="utf-8")

    result = v211_setup_cli.cleanup_four_engine_assets(root, confirmed=True)

    assert result["status"] == "removed"
    assert result["removed"] is True
    assert not archive.exists()
    assert not engine.exists()
    assert not (root / "manifest.json").exists()
    assert not (root / "setup-complete.flag").exists()
    assert unknown.read_text(encoding="utf-8") == "keep this unrelated file"
    assert root.is_dir()
    assert result["unknown_entries_preserved"] is True


def test_uninstall_cache_cleanup_rejects_paths_outside_profile_localappdata(tmp_path):
    unsafe = tmp_path / "customer-artwork" / "V211-FourAI-QA"
    unsafe.mkdir(parents=True)

    with pytest.raises(ValueError, match="outside the approved LocalAppData"):
        v211_setup_cli.cleanup_four_engine_assets(unsafe, confirmed=True)

    assert unsafe.is_dir()


def test_uninstall_cache_cleanup_does_not_follow_child_directory_symlinks(tmp_path):
    root = _four_ai_cache_root(tmp_path)
    engines = root / "engines"
    engines.mkdir(parents=True)
    external = tmp_path / "external-models"
    external.mkdir()
    external_file = external / "keep.bin"
    external_file.write_bytes(b"must remain outside the cache")
    link = engines / "external-link"
    try:
        link.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable on this runner")

    v211_setup_cli.cleanup_four_engine_assets(root, confirmed=True)

    assert external_file.is_file()
    assert not link.exists()
    assert not engines.exists()


def test_uninstall_cache_cleanup_rejects_cache_root_symlink(tmp_path):
    expected = _four_ai_cache_root(tmp_path)
    expected.parent.mkdir(parents=True)
    external = tmp_path / "external-cache"
    external.mkdir()
    try:
        expected.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable on this runner")

    with pytest.raises(ValueError, match="not a safe ordinary directory"):
        v211_setup_cli.cleanup_four_engine_assets(expected, confirmed=True)

    assert external.is_dir()

