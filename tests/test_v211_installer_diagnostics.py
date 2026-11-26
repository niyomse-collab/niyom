"""Privacy-safe diagnostic logging for the V2.1.1 installer."""
from signprint_ai import v211_setup_cli


def test_diagnostic_log_identifies_engine_and_exception_without_private_paths(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "installer-setup.log"
    monkeypatch.setattr(v211_setup_cli, "_log_path", lambda: log_path)
    private_path = r"C:\\Users\\Customer\\Artwork\\secret-sign.png"

    v211_setup_cli._record_diagnostic(
        ValueError("real_esrgan: SHA256 mismatch at " + private_path)
    )

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
