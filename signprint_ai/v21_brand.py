"""V2.1 UI label; approved V1 release metadata remains unchanged."""
import sys
from .release_info import load_release_info


def release_label(default="v2"):
    info = load_release_info()
    if info.get("channel") == "v2":
        return "v2.1" if info.get("version", "").startswith("2.1.") else "v2"
    if getattr(sys, "frozen", False):
        return info.get("channel", default)
    return "v2.1"
