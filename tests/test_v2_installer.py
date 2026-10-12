from pathlib import Path
import hashlib
import json
import sys

import pytest

from signprint_ai.release_info import load_release_info, release_label
from tools.generate_v2_download_installer import generate
from signprint_ai.v2_output import V2_OUTPUT_FOLDER, output_path


def test_frozen_v2_metadata_with_windows_bom(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    info = {'channel':'v2', 'version':'2.0.0-beta.1', 'source_commit':'a'*40}
    (tmp_path/'build_info.json').write_text(json.dumps(info),encoding='utf-8-sig')
    assert load_release_info() == info and release_label() == 'v2'


def test_legacy_package_without_metadata(monkeypatch,tmp_path):
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert release_label() == 'v1'


def test_download_installer_embeds_real_hashes_and_complete_payload(tmp_path):
    exe = tmp_path/'NiyomSilp-Design-v2-Setup.exe'
    binary = tmp_path/'NiyomSilp-Design-v2-Setup-1.bin'
    exe.write_bytes(b'installer')
    binary.write_bytes(b'verified runtime and models')
    output = tmp_path/'download.iss'
    manifest = generate(tmp_path,'niyomse-collab/niyom','v2-large-images-1',
                        '2.0.0-beta.1',output,tmp_path/'icon.ico')
    assert len(manifest['payloads']) == 2
    script = output.read_text('utf-8-sig')
    for payload in manifest['payloads']:
        assert payload['sha256'] == hashlib.sha256((tmp_path/payload['name']).read_bytes()).hexdigest()
        assert payload['sha256'] in script and payload['url'] in script
    assert json.loads((tmp_path/'INSTALLER_MANIFEST.json').read_text()) == manifest
    assert '@@' not in script


def test_partial_installer_payload_cannot_be_published(tmp_path):
    (tmp_path/'NiyomSilp-Design-v2-Setup.exe').write_bytes(b'partial')
    with pytest.raises(ValueError,match='Complete offline'):
        generate(tmp_path,'niyomse-collab/niyom','v2-large-images-1',
                 '2.0.0-beta.1',tmp_path/'download.iss',tmp_path/'icon.ico')


def test_v1_and_v2_installers_have_distinct_ids_and_paths():
    root = Path(__file__).resolve().parents[1]
    v1 = (root / "installer.iss").read_text(encoding="utf-8")
    v2 = (root / "installer_v2.iss").read_text(encoding="utf-8")
    def item(script, name):
        return next(line for line in script.splitlines() if line.startswith(name + "=")).split("=", 1)[1]
    assert item(v2, "AppId") != item(v1, "AppId")
    assert item(v1, "DefaultDirName").endswith(r"\NiyomSilpDesignV1")
    assert item(v2, "DefaultDirName").endswith(r"\NiyomSilpDesignV2")
    assert item(v1, "DefaultGroupName") == item(v2, "DefaultGroupName")
    assert item(v1, "OutputBaseFilename") != item(v2, "OutputBaseFilename")
    assert "UsePreviousAppDir=no" in v2
    assert "function PrepareToInstall" in v2
    assert "NiyomSilpDesignV1" in v2
    assert "RegQueryStringValue" in v2
    assert "[InstallDelete]" not in v2
    assert "NiyomSilp Design v2" in v2


def test_v2_output_defaults_to_separate_folder_and_keeps_v1_output(tmp_path):
    original = tmp_path / "poster.png"
    original.write_bytes(b"original")
    v1 = tmp_path / "poster_Niyomsil_AI.png"
    v1.write_bytes(b"v1 protected result")
    target = output_path(original, "", "PNG", "RGB")
    assert target.parent == tmp_path / V2_OUTPUT_FOLDER
    assert "_NiyomSilp_V2_AI" in target.stem
    assert target != v1
    assert v1.read_bytes() == b"v1 protected result"


def test_v2_output_never_reuses_an_existing_file_or_a_queued_name(tmp_path):
    original = tmp_path / "poster.jpg"
    original.write_bytes(b"original")
    first = output_path(original, tmp_path, "TIFF", "CMYK")
    first.write_bytes(b"completed v2 output")
    second = output_path(original, tmp_path, "TIFF", "CMYK")
    third = output_path(original, tmp_path, "TIFF", "CMYK", occupied={second})
    assert len({first, second, third}) == 3
    assert second.name.endswith("_2.tif") and third.name.endswith("_3.tif")
    assert first.read_bytes() == b"completed v2 output"


def test_v2_output_rejects_explicit_v1_install_folder(tmp_path):
    v1_folder = tmp_path / "NiyomSilpDesignV1" / "outputs"
    with pytest.raises(ValueError, match="V1"):
        output_path(tmp_path / "poster.png", v1_folder, "PNG", "RGB")
