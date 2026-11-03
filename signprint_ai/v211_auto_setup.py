"""One-time install of four independently licensed engines for V2.1.1 QA.

Only call provision() after explicit confirmation from the desktop user.
The files go into private LOCALAPPDATA; no binaries or model weights are
redistributed with V2, and no image is uploaded. Subsequent enhancement is
offline. The approved V2 print/export pipeline remains unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path


def qa_root() -> Path:
    appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return appdata / "NiyomSilp" / "V211-FourAI-QA"


def default_manifest() -> Path:
    return qa_root() / "manifest.json"


def needs_initial_setup() -> bool:
    if os.environ.get("NIYOMSIL_V211_FOUR_AI") == "0":
        return False
    if os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip():
        return False
    return not default_manifest().is_file()


def provision_after_consent() -> dict:
    """Download four SHA256-pinned upstream Windows ZIPs on first consent only.

    Called on a worker thread to keep Tk responsive. Failed hash/ZIP checks
    must fail closed. Existing installs are never overwritten, even when
    only partially present; a human must review/correct their QA directory.
    """
    from tools.v211_official_assets_audit import PACKAGES, download_archive
    from tools.v211_provision_four_engines import provision_from_archives
    from tools.v211_real_engine_manifest import load_real_engine_manifest

    root = qa_root()
    manifest = default_manifest()
    if manifest.exists():
        verified = load_real_engine_manifest(manifest)
        return {"status": "already_installed", "manifest": str(manifest),
                "verified_engine_names": sorted(verified)}
    archives = root / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    for name, package in PACKAGES.items():
        target = archives / (name + ".zip")
        if not target.exists():
            download_archive(package["url"], target)
    details = provision_from_archives(archives, root / "engines", manifest)
    verified = load_real_engine_manifest(manifest)
    if len(verified) != 4:
        raise RuntimeError("four-engine installed manifest did not validate")
    return {
        "status": "installed_for_offline_qa",
        "manifest": str(manifest),
        "verified_engine_names": sorted(verified),
        "quality_certified": False,
        "real_inference_verified_on_this_pc": False,
        "no_v2_stable_change": True,
        "provision_metadata": details,
    }
