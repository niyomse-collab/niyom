from pathlib import Path
import hashlib
import json
import sys

import pytest

from signprint_ai.release_info import load_release_info, release_label
from tools.generate_v2_download_installer import generate


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
