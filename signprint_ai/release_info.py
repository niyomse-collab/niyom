"""Release metadata bundled with an installer, independent of model settings."""
from pathlib import Path
import json
import sys


def load_release_info():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    path = root / "build_info.json"
    if not path.is_file():
        return {"channel": "v1", "version": "1.0.1"}
    info = json.loads(path.read_text(encoding="utf-8-sig"))
    if info.get("channel") not in ("v1", "v2"):
        raise ValueError("Invalid installer release channel")
    return info


def release_label(default="v1"):
    return load_release_info().get("channel", default)
