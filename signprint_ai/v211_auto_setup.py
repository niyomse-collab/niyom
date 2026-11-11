"""Installer-time provisioning of four independently licensed V2.1.1 engines.

Only the experimental installer's explicit all-four consent task invokes this
module. The files go into private LOCALAPPDATA; no binaries or model weights
are redistributed with V2, and no image is uploaded. Subsequent enhancement
is offline. The approved V2 print/export pipeline remains unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path


def qa_root() -> Path:
    appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return appdata / "NiyomSilp" / "V211-FourAI-QA"


def default_manifest() -> Path:
    return qa_root() / "manifest.json"


def selected_manifest() -> Path:
    """Return the same manifest path for setup checks and consented provisioning.

    The explicit environment override is used by portable/test installations.
    Resolving it here prevents setup from writing the default manifest while
    the runtime continues reading a different, incomplete override.
    """
    override = os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip()
    path = Path(override).expanduser() if override else default_manifest()
    return path.resolve()


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
    manifest = selected_manifest()
    if manifest.exists():
        verified = load_real_engine_manifest(manifest)
        if set(verified) != {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}:
            raise RuntimeError("existing manifest does not verify all four engines")
        return {
            "status": "already_installed",
            "manifest": str(manifest),
            "manifest_source": (
                "explicit_override"
                if os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip()
                else "localappdata_default"
            ),
            "verified_engine_names": sorted(verified),
        }
    archives = root / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    for name, package in PACKAGES.items():
        target = archives / (name + ".zip")
        ensure_verified_archive(target, package)
    details = provision_from_archives(archives, root / "engines", manifest)
    verified = load_real_engine_manifest(manifest)
    if set(verified) != {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}:
        raise RuntimeError("four-engine installed manifest did not validate")
    return {
        "status": "installed_for_offline_qa",
        "manifest": str(manifest),
        "manifest_source": (
            "explicit_override"
            if os.environ.get("NIYOMSIL_V211_FOUR_AI_MANIFEST", "").strip()
            else "localappdata_default"
        ),
        "verified_engine_names": sorted(verified),
        "quality_certified": False,
        "real_inference_verified_on_this_pc": False,
        "no_v2_stable_change": True,
        "provision_metadata": details,
    }
