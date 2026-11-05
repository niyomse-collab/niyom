"""Offline tests for official model-archive audit. No external programs run."""
import hashlib
import io
import zipfile

import pytest

from tools import v211_official_assets_audit as assets
from tools.v211_official_assets_audit import audit_archive, verify_archive_hash


def test_archive_digest_pin_is_checked(tmp_path):
    path = tmp_path / "asset.zip"
    with zipfile.ZipFile(path, "w") as f:
        f.writestr("models/realcugan.param", "net graph")
        f.writestr("models/realcugan.bin", b"weights")
        f.writestr("realcugan-ncnn-vulkan.exe", b"fake")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    result = verify_archive_hash(path, expected)
    assert result["release_digest_verified"] is True
    assert result["requires_independent_digest_approval"] is False
    audit = audit_archive(path)
    assert "realcugan-ncnn-vulkan.exe" in audit["candidate_executables"]
    assert audit["model_or_binary_file_count"] == 2
    assert audit["archive_member_audit_passed"] is True


def test_archives_without_published_digest_are_not_certified(tmp_path):
    path = tmp_path / "older-release.zip"
    path.write_bytes(b"downloaded")
    result = verify_archive_hash(path, None)
    assert not result["release_digest_verified"]
    assert result["requires_independent_digest_approval"]


def test_archive_wrong_digest_fails_closed(tmp_path):
    path = tmp_path / "asset.zip"
    path.write_bytes(b"test")
    with pytest.raises(ValueError, match="mismatch"):
        verify_archive_hash(path, "0" * 64)


def test_archive_path_traversal_rejected(tmp_path):
    path = tmp_path / "asset.zip"
    with zipfile.ZipFile(path, "w") as f:
        f.writestr("../outside.exe", "unsafe")
    with pytest.raises(ValueError, match="unsafe"):
        audit_archive(path)


def test_archive_non_zip_rejected(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_bytes(b"not zip")
    with pytest.raises(ValueError, match="ZIP"):
        audit_archive(path)


def test_archive_rejects_duplicate_windows_casefolded_paths(tmp_path):
    path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("models/Net.bin", b"a")
        archive.writestr("models/net.bin", b"b")
    with pytest.raises(ValueError, match="duplicate Windows path"):
        audit_archive(path)


def test_archive_rejects_windows_drive_path(tmp_path):
    path = tmp_path / "drive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("C:/Windows/untrusted.exe", b"x")
    with pytest.raises(ValueError, match="unsafe path"):
        audit_archive(path)


def test_archive_rejects_unix_symlink(tmp_path):
    path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("models/link.bin")
    info.create_system = 3
    info.external_attr = (0o120777 << 16)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, "../outside.bin")
    with pytest.raises(ValueError, match="symbolic link"):
        audit_archive(path)


@pytest.mark.parametrize("member", [
    "CON.txt", "models/NUL.bin", "models/COM1.param",
    "models/weights.bin:stream", "models/weights.bin.",
    "models/weights.bin ", "models/weights?.bin",
])
def test_archive_rejects_unsafe_windows_member_names(tmp_path, member):
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, b"not safe on Windows")
    with pytest.raises(ValueError, match="unsafe Windows path"):
        audit_archive(path)

class _FakeResponse:
    def __init__(self, payload, *, fail_after=None, headers=None):
        self.payload = payload
        self.fail_after = fail_after
        self.headers = headers or {}
        self.position = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size):
        if self.fail_after is not None and self.position >= self.fail_after:
            raise OSError("synthetic connection reset")
        end = min(self.position + size, len(self.payload))
        if self.fail_after is not None:
            end = min(end, self.fail_after)
        chunk = self.payload[self.position:end]
        self.position = end
        return chunk


def _valid_zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("engine.exe", b"synthetic executable")
        archive.writestr("models/net.param", b"network")
        archive.writestr("models/net.bin", b"weights")
    return buffer.getvalue()


def test_download_publishes_only_after_zip_and_digest_validation(tmp_path, monkeypatch):
    payload = _valid_zip_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    target = tmp_path / "engine.zip"
    target.write_bytes(b"previous verified archive")
    response = _FakeResponse(
        payload, headers={"Content-Length": str(len(payload))}
    )
    monkeypatch.setattr(assets.urllib.request, "urlopen", lambda *a, **k: response)

    result = assets.download_archive(
        "https://example.invalid/engine.zip", target, expected_sha256=digest
    )

    assert target.read_bytes() == payload
    assert result["release_digest_verified"] is True
    assert audit_archive(target)["archive_member_audit_passed"] is True
    assert list(tmp_path.glob("*.part")) == []
    assert list(tmp_path.glob(".*.part")) == []


def test_failed_digest_keeps_previous_archive_and_removes_partial(tmp_path, monkeypatch):
    payload = _valid_zip_bytes()
    target = tmp_path / "engine.zip"
    previous = b"previous verified archive"
    target.write_bytes(previous)
    response = _FakeResponse(payload)
    monkeypatch.setattr(assets.urllib.request, "urlopen", lambda *a, **k: response)

    with pytest.raises(ValueError, match="mismatch"):
        assets.download_archive(
            "https://example.invalid/engine.zip", target,
            expected_sha256="0" * 64,
        )

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".*.part")) == []


def test_interrupted_download_keeps_previous_archive_and_removes_partial(tmp_path, monkeypatch):
    target = tmp_path / "engine.zip"
    previous = b"previous verified archive"
    target.write_bytes(previous)
    response = _FakeResponse(b"partial-download", fail_after=5)
    monkeypatch.setattr(assets.urllib.request, "urlopen", lambda *a, **k: response)

    expected = hashlib.sha256(b"partial-download").hexdigest()
    with pytest.raises(OSError, match="connection reset"):
        assets.download_archive(
            "https://example.invalid/engine.zip", target,
            expected_sha256=expected,
        )

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".*.part")) == []



def test_download_refuses_to_start_without_a_sha256_pin(tmp_path, monkeypatch):
    target = tmp_path / "engine.zip"
    previous = b"previous verified archive"
    target.write_bytes(previous)

    def unexpected_network(*args, **kwargs):
        pytest.fail("download must fail before opening the network without a pin")

    monkeypatch.setattr(assets.urllib.request, "urlopen", unexpected_network)
    with pytest.raises(ValueError, match="SHA256 pin"):
        assets.download_archive("https://example.invalid/engine.zip", target)

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".*.part")) == []


def test_unsafe_downloaded_zip_never_replaces_existing_archive(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.exe", b"unsafe")
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    target = tmp_path / "engine.zip"
    previous = b"previous verified archive"
    target.write_bytes(previous)
    response = _FakeResponse(payload)
    monkeypatch.setattr(assets.urllib.request, "urlopen", lambda *a, **k: response)

    with pytest.raises(ValueError, match="unsafe"):
        assets.download_archive(
            "https://example.invalid/engine.zip", target, expected_sha256=digest
        )

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".*.part")) == []

