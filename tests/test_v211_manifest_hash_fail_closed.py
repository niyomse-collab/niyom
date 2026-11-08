"""Fail-closed manifest contract tests; these do NOT certify real inference."""
import hashlib
import json
from pathlib import Path

import pytest

from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_official_assets_audit import PACKAGES
from tools.v211_real_engine_manifest import (
    EXECUTABLES,
    MODEL_DIRECTORIES,
    MODEL_NAMES,
    load_real_engine_manifest,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path):
    data = {}
    real_esrgan_executable = None
    real_cugan_model = None

    for engine in ENGINES:
        engine_root = tmp_path / "engines" / engine
        engine_root.mkdir(parents=True)
        exe = engine_root / EXECUTABLES[engine]
        exe.write_bytes(("synthetic executable fixture: " + engine).encode("ascii"))

        if engine == "anime4k":
            assets = []
            args = ["-i", "{input}", "-o", "{output}", "-f", "2"]
        else:
            model_dir = engine_root / MODEL_DIRECTORIES[engine]
            model_dir.mkdir()
            param = model_dir / "synthetic.param"
            weights = model_dir / "synthetic.bin"
            param.write_bytes(b"synthetic ncnn parameter")
            weights.write_bytes(b"synthetic model bytes")
            assets = [
                {"path": str(param.resolve()), "sha256": _sha(param)},
                {"path": str(weights.resolve()), "sha256": _sha(weights)},
            ]
            args = [
                "-i", "{input}", "-o", "{output}",
                "-m", str(model_dir.resolve()),
                "-n", MODEL_NAMES[engine],
                "-s", "2", "-t", "128",
            ]
            if engine == "real_cugan":
                real_cugan_model = weights

        package = PACKAGES[engine]
        archive_sha = package.get("release_sha256") or package.get("observed_sha256")
        data[engine] = {
            "executable": str(exe.resolve()),
            "executable_sha256": _sha(exe),
            "model_assets": assets,
            "args": args,
            "timeout_seconds": 1800,
            "provenance": {
                "source_url": package["url"],
                "license_name": package["license"],
                "license_url": package["license_url"],
                "additional_license_notices": package.get("additional_license_notices", []),
            },
            "archive_sha256": archive_sha,
            "archive_digest_source": (
                "published_release_sha256"
                if package.get("release_sha256")
                else "observed_ci_sha256"
            ),
        }
        if engine == "anime4k":
            data[engine]["embedded_algorithm"] = True
        if engine == "real_esrgan":
            real_esrgan_executable = exe

    return data, real_esrgan_executable, real_cugan_model


def _load(tmp_path, data):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return load_real_engine_manifest(manifest)


def test_all_four_engines_require_repository_pinned_provenance_and_sha256(tmp_path):
    data, _, _ = _fixture(tmp_path)
    assert set(_load(tmp_path, data)) == set(ENGINES)


@pytest.mark.parametrize("field", ["executable_sha256", "model_sha256"])
def test_missing_hash_is_rejected(tmp_path, field):
    data, _, _ = _fixture(tmp_path)
    if field == "executable_sha256":
        del data["waifu2x"]["executable_sha256"]
    else:
        del data["real_cugan"]["model_assets"][0]["sha256"]
    with pytest.raises(ValueError, match="64-character hex digest"):
        _load(tmp_path, data)


@pytest.mark.parametrize("target", ["executable", "model"])
def test_modified_bytes_are_rejected(tmp_path, target):
    data, exe, model = _fixture(tmp_path)
    (exe if target == "executable" else model).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        _load(tmp_path, data)


def test_unhashed_directory_asset_is_rejected(tmp_path):
    data, _, model = _fixture(tmp_path)
    data["anime4k"]["model_assets"] = [{"path": str(model.parent), "sha256": "0" * 64}]
    with pytest.raises(ValueError, match="individual files with SHA256"):
        _load(tmp_path, data)


def test_hand_edited_archive_pin_is_rejected(tmp_path):
    data, _, _ = _fixture(tmp_path)
    data["real_esrgan"]["archive_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="repository-pinned release"):
        _load(tmp_path, data)


def test_hand_edited_source_or_license_provenance_is_rejected(tmp_path):
    data, _, _ = _fixture(tmp_path)
    data["waifu2x"]["provenance"]["source_url"] = "https://example.invalid/other.zip"
    with pytest.raises(ValueError, match="provenance differs"):
        _load(tmp_path, data)


def test_executable_outside_its_engine_root_is_rejected(tmp_path):
    data, exe, _ = _fixture(tmp_path)
    external = tmp_path / "realesrgan-ncnn-vulkan.exe"
    external.write_bytes(exe.read_bytes())
    data["real_esrgan"]["executable"] = str(external.resolve())
    data["real_esrgan"]["executable_sha256"] = _sha(external)
    with pytest.raises(ValueError, match="isolated engine directory"):
        _load(tmp_path, data)


def test_wrong_official_executable_name_is_rejected(tmp_path):
    data, _, _ = _fixture(tmp_path)
    wrong = tmp_path / "engines" / "real_esrgan" / "other.exe"
    original = Path(data["real_esrgan"]["executable"])
    wrong.write_bytes(original.read_bytes())
    data["real_esrgan"]["executable"] = str(wrong.resolve())
    data["real_esrgan"]["executable_sha256"] = _sha(wrong)
    with pytest.raises(ValueError, match="unexpected official executable name"):
        _load(tmp_path, data)


def test_unpinned_cli_arguments_are_rejected(tmp_path):
    data, _, _ = _fixture(tmp_path)
    data["real_cugan"]["args"][-1] = "999"
    with pytest.raises(ValueError, match="pinned NCNN"):
        _load(tmp_path, data)


def test_model_asset_outside_engine_root_is_rejected(tmp_path):
    data, _, _ = _fixture(tmp_path)
    external = tmp_path / "external-model.bin"
    external.write_bytes(b"synthetic external model")
    data["real_cugan"]["model_assets"][0] = {
        "path": str(external.resolve()),
        "sha256": _sha(external),
    }
    with pytest.raises(ValueError, match="outside its isolated engine directory"):
        _load(tmp_path, data)
