"""Fail-closed manifest contract tests; these do NOT certify real inference."""
import hashlib
import json
from pathlib import Path

import pytest

from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_real_engine_manifest import load_real_engine_manifest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path):
    exe = tmp_path / "engine.exe"
    model = tmp_path / "model.bin"
    exe.write_bytes(b"test executable; not an inference engine")
    model.write_bytes(b"test checkpoint; not model weights")
    data = {
        engine: {
            "executable": str(exe),
            "executable_sha256": _sha(exe),
            "model_assets": [{"path": str(model), "sha256": _sha(model)}],
            "provenance": {
                "source_url": "https://example.org/source",
                "license_name": "test-only",
                "license_url": "https://example.org/license",
            },
            "args": ["--input", "{input}", "--output", "{output}"],
        }
        for engine in ENGINES
    }
    return data, exe, model


def _load(tmp_path, data):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return load_real_engine_manifest(manifest)


def test_all_four_engines_require_valid_sha256(tmp_path):
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
    data["anime4k"]["model_assets"] = [str(model.parent)]
    with pytest.raises(ValueError, match="individual files with SHA256"):
        _load(tmp_path, data)
