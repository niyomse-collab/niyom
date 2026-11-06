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
    """Return false only when the selected manifest verifies all four engines.

    A stale, truncated, or hand-created manifest must never suppress setup by
    mere file existence. An explicit manifest override is validated exactly
    like the default LOCALAPPDATA manifest.
    """
    if os.environ.get("NIYOMSIL_V211_FOUR_AI") == "0":
        return False

    override = os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip()
    manifest = Path(override) if override else default_manifest()
    try:
        from tools.v211_real_engine_manifest import load_real_engine_manifest

        verified = load_real_engine_manifest(manifest)
        return set(verified) != {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
    except (ImportError, OSError, ValueError, KeyError, TypeError):
        return True


def provision_after_consent() -> dict:
    """Download four SHA256-pinned upstream Windows ZIPs on first consent only.

    Called on a worker thread to keep Tk responsive. Failed hash/ZIP checks
    must fail closed. Existing installs are never overwritten, even when
    only partially present; a human must review/correct their QA directory.
    """
    from tools.v211_official_assets_audit import PACKAGES
    from tools.v211_provision_four_engines import (
        ensure_verified_archive, provision_from_archives,
    )
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
        ensure_verified_archive(target, package)
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
