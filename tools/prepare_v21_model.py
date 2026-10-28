"""Fetch the pinned, official V2.1 graphic model in a clean V2 build checkout."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = 'f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da'
MODEL_URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth'


def main():
    metadata=ROOT/'build_info.json'
    if metadata.exists() and json.loads(metadata.read_text(encoding='utf-8-sig')).get('channel')!='v2':
        raise RuntimeError('Use a clean V2.1 checkout; do not modify V1 models')
    destination=ROOT/'models'/'RealESRGAN_x4plus_anime_6B.pth'
    destination.parent.mkdir(exist_ok=True)
    temporary=destination.with_suffix('.download')
    try:
        with urllib.request.urlopen(MODEL_URL,timeout=120) as source, temporary.open('wb') as output:
            while chunk:=source.read(1024*1024):output.write(chunk)
        with temporary.open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==MODEL_SHA256, 'V2.1 model hash mismatch'
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__=='__main__':main()
