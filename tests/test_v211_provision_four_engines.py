"""Offline packaging tests: synthetic ZIPs only, never report real AI inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from tools import v211_provision_four_engines as provision
from tools.v211_real_engine_manifest import load_real_engine_manifest


def _fake_archives(tmp_path, monkeypatch, *, missing_weights=False):
    archives = tmp_path / "archives"
    archives.mkdir()
    configs = {}
    for engine, executable in provision.EXECUTABLES.items():
        path = archives / (engine + ".zip")
        prefix = "portable-release/"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(prefix + executable, engine.encode())
            if engine != "anime4k":
                folder = provision.MODEL_DIRECTORIES[engine]
                z.writestr(prefix + folder + "/test.param", b"7767517\n10 10\n")
                if not (missing_weights and engine == "real_cugan"):
                    z.writestr(prefix + folder + "/test.bin", b"weights")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        configs[engine] = {
            "release": "test",
            "url": "https://github.com/example/synthetic-fixture",
            "license": "test-only",
            "license_url": "https://github.com/example/synthetic-fixture/LICENSE",
            "release_sha256": sha,
        }
    monkeypatch.setattr(provision, "PACKAGES", configs)
    return archives


def test_create_verified_manifest_from_four_archives(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    manifest_path = tmp_path / "qa-manifest.json"
    result = provision.provision_from_archives(
        archives, tmp_path / "installed-engines", manifest_path
    )
    assert not result["real_inference_verified"]
    assert not result["quality_certified"]
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(data) == {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
    assert data["anime4k"]["embedded_algorithm"] is True
    assert data["anime4k"]["model_assets"] == []
    assert len(data["waifu2x"]["model_assets"]) == 2
    assert data["anime4k"]["args"][-2:] == ["-f", "2"]
    assert "realesrgan-x4plus" in data["real_esrgan"]["args"]
    assert load_real_engine_manifest(manifest_path)["anime4k"].argv[0].endswith("ac_cli.exe")
    assert all(Path(v["executable"]).is_file() for v in data.values())


def test_no_manifest_when_archive_hash_changes(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    (archives / "anime4k.zip").write_bytes(b"tampered")
    install = tmp_path / "installed"
    manifest = tmp_path / "manifest.json"
    with pytest.raises(ValueError, match="mismatch"):
        provision.provision_from_archives(archives, install, manifest)
    assert not manifest.exists()
    assert not install.exists()


def test_missing_neural_weights_never_produces_ready_manifest(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch, missing_weights=True)
    manifest = tmp_path / "manifest.json"
    with pytest.raises(ValueError, match="binary weights"):
        provision.provision_from_archives(archives, tmp_path / "installed", manifest)
    assert not manifest.exists()


def test_repeat_install_refuses_overwrite(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    install = tmp_path / "installed"
    provision.provision_from_archives(archives, install, tmp_path / "manifest.json")
    with pytest.raises(FileExistsError, match="existing installation"):
        provision.provision_from_archives(archives, install, tmp_path / "second.json")



def test_failed_staging_rolls_back_every_engine_directory(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    install = tmp_path / "installed"
    manifest = tmp_path / "manifest.json"
    original_manifest_entry = provision.manifest_entry

    def fail_during_third_engine(engine, directory, package, digest):
        if engine == "real_cugan":
            raise RuntimeError("synthetic staging failure")
        return original_manifest_entry(engine, directory, package, digest)

    monkeypatch.setattr(provision, "manifest_entry", fail_during_third_engine)
    with pytest.raises(RuntimeError, match="synthetic staging failure"):
        provision.provision_from_archives(archives, install, manifest)

    assert not manifest.exists()
    assert not any((install / engine).exists() for engine in provision.PACKAGES)
    assert list(install.iterdir()) == []


def test_manifest_publish_failure_rolls_back_promoted_directories(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    install = tmp_path / "installed"
    manifest = tmp_path / "manifest.json"

    def fail_manifest_publish(path, payload):
        raise OSError("synthetic manifest disk failure")

    monkeypatch.setattr(provision, "_write_manifest_exclusive", fail_manifest_publish)
    with pytest.raises(OSError, match="synthetic manifest disk failure"):
        provision.provision_from_archives(archives, install, manifest)

    assert not manifest.exists()
    assert not any((install / engine).exists() for engine in provision.PACKAGES)
    assert list(install.iterdir()) == []


def test_existing_verified_archive_is_reused_without_download(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    package = provision.PACKAGES["real_esrgan"]
    target = archives / "real_esrgan.zip"

    def unexpected_download(*args, **kwargs):
        pytest.fail("verified existing archive should be reused")

    monkeypatch.setattr(provision, "download_archive", unexpected_download)
    result = provision.ensure_verified_archive(target, package)

    assert result["status"] == "already_verified"
    assert target.is_file()


def test_invalid_cached_archive_uses_pinned_download_retry(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    package = provision.PACKAGES["real_esrgan"]
    target = archives / "real_esrgan.zip"
    valid_bytes = target.read_bytes()
    target.write_bytes(b"interrupted partial archive")
    calls = []

    def verified_replacement(url, destination, release_sha256=None, observed_sha256=None):
        calls.append((url, Path(destination), release_sha256, observed_sha256))
        Path(destination).write_bytes(valid_bytes)
        return {"archive_sha256": hashlib.sha256(valid_bytes).hexdigest()}

    monkeypatch.setattr(provision, "download_archive", verified_replacement)
    result = provision.ensure_verified_archive(target, package)

    assert result["status"] == "downloaded_verified"
    assert len(calls) == 1
    assert calls[0][0] == package["url"]
    assert calls[0][1] == target
    assert calls[0][2] == package.get("release_sha256")
    assert calls[0][3] == package.get("observed_sha256")
    assert target.read_bytes() == valid_bytes


def test_embedded_exception_only_allows_hash_pinned_anime4k(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    manifest = tmp_path / "manifest.json"
    provision.provision_from_archives(archives, tmp_path / "installed", manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["waifu2x"]["embedded_algorithm"] = True
    data["waifu2x"]["model_assets"] = []
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="exemption forbidden"):
        load_real_engine_manifest(manifest)


def test_embedded_anime4k_is_not_allowed_with_wrong_executable_hash(tmp_path, monkeypatch):
    archives = _fake_archives(tmp_path, monkeypatch)
    manifest = tmp_path / "manifest.json"
    provision.provision_from_archives(archives, tmp_path / "installed", manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["anime4k"]["executable_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_real_engine_manifest(manifest)
