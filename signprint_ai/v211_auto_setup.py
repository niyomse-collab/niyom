"""Consent-gated provisioning of the four V2.1.1 research engines.

The experimental installer checkbox or the editor's one-time first-launch
Yes/No prompt may authorize setup. A No decision is recorded locally so the
editor does not repeat the prompt. No network access occurs during the status
check; downloads begin only after affirmative consent. The approved V2
print/export pipeline remains unchanged.
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


def initial_setup_state() -> dict:
    """Inspect local state only; never download or create files."""
    from .v211_setup_cli import _validate_four_ai_data_root
    from tools.v211_real_engine_manifest import load_real_engine_manifest

    root = _validate_four_ai_data_root(qa_root())
    manifest = selected_manifest()
    if manifest.is_symlink() or (manifest.exists() and not manifest.is_file()):
        return {"status": "invalid_existing_manifest"}
    if manifest.exists():
        try:
            verified = load_real_engine_manifest(manifest)
        except Exception:
            return {"status": "invalid_existing_manifest"}
        required = {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
        if set(verified) != required:
            return {"status": "invalid_existing_manifest"}
        return {
            "status": "already_installed",
            "manifest": str(manifest),
            "verified_engine_names": sorted(verified),
        }

    marker = root / "setup-declined.flag"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        return {"status": "invalid_decline_marker"}
    if marker.is_file():
        return {"status": "declined"}
    return {"status": "needs_consent"}


def record_setup_declined() -> dict:
    """Persist the user's No decision locally without touching model files."""
    from .v211_setup_cli import _validate_four_ai_data_root

    root = _validate_four_ai_data_root(qa_root())
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "setup-declined.flag"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise RuntimeError("four-engine decline marker is not a regular file")
    try:
        with marker.open("x", encoding="utf-8") as stream:
            stream.write("NiyomSilp V2.1.1 four-engine setup declined by user\\n")
    except FileExistsError:
        pass
    return {"status": "declined", "marker": str(marker)}


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
    declined_marker = root / "setup-declined.flag"
    if manifest.exists():
        verified = load_real_engine_manifest(manifest)
        if set(verified) != {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}:
            raise RuntimeError("existing manifest does not verify all four engines")
        declined_marker.unlink(missing_ok=True)
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
    declined_marker.unlink(missing_ok=True)
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
