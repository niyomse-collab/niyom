"""Privacy-safe diagnostic logging for the V2.1.1 installer."""
from signprint_ai import v211_setup_cli


def test_diagnostic_log_identifies_engine_and_exception_without_private_paths(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)
    private_path = r"C:\\Users\\Customer\\Artwork\\secret-sign.png"

    exc = ValueError("SHA256 mismatch at " + private_path)
    exc.engine = "real_esrgan"
    v211_setup_cli._record_diagnostic(exc)

    content = log_path.read_text(encoding="utf-8")
    assert "DIAGNOSTIC code=verification_failed" in content
    assert "engine=real_esrgan" in content
    assert "exception=ValueError" in content
    assert private_path not in content
    assert "SHA256 mismatch" not in content


def test_diagnostic_log_uses_unknown_engine_when_not_identifiable(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    v211_setup_cli._record_diagnostic(RuntimeError("private path /tmp/customer.png"))

    content = log_path.read_text(encoding="utf-8")
    assert "engine=unknown" in content
    assert "exception=RuntimeError" in content
    assert "customer.png" not in content



def test_diagnostic_entries_are_separate_lines_and_never_embed_literal_newline_tokens(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    v211_setup_cli._record_diagnostic(ValueError("private path C:\\customer\\one.png"))
    v211_setup_cli._record_diagnostic(RuntimeError("private path C:\\customer\\two.png"))

    content = log_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert len(lines) == 2
    assert all(line.startswith("DIAGNOSTIC code=") for line in lines)
    assert content.endswith("\n")
    assert "\\n" not in content
    assert "customer" not in content



def test_diagnostic_log_rejects_non_string_engine_context(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    exc = ValueError("private path /customer/artwork.png")
    exc.engine = ["real_esrgan"]
    v211_setup_cli._record_diagnostic(exc)

    content = log_path.read_text(encoding="utf-8")
    assert "engine=unknown" in content
    assert "real_esrgan" not in content
    assert "customer" not in content


def test_provision_failure_always_records_engine_stage_even_in_silent_cli_path(
    monkeypatch, tmp_path
):
    import pytest

    marker = tmp_path / "setup-complete.flag"
    pending = tmp_path / "setup-pending.flag"
    log_path = tmp_path / "installer-setup.log"
    pending.write_text("pending", encoding="ascii")
    monkeypatch.setattr(v211_setup_cli, "completion_marker_path", lambda: marker)
    monkeypatch.setattr(v211_setup_cli, "pending_marker_path", lambda: pending)
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)

    def fail_install():
        exc = ValueError("private customer path must never be logged")
        exc.engine = "waifu2x"
        exc.stage = "archive_hash_or_structure"
        raise exc

    monkeypatch.setattr(v211_setup_cli, "install_for_offline_use", fail_install)

    with pytest.raises(ValueError):
        v211_setup_cli._run_and_publish_success()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "DIAGNOSTIC code=verification_failed engine=waifu2x "
        "stage=archive_hash_or_structure exception=ValueError",
        "FAILED verification_failed",
    ]
    assert not marker.exists()
    assert pending.is_file()
    assert "customer" not in log_path.read_text(encoding="utf-8")
