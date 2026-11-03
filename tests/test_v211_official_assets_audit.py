"""Offline tests for official model-archive audit. No external programs run."""
import hashlib
import zipfile

import pytest

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
