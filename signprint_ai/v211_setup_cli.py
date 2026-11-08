"""Consent-gated provisioning entry point for the V2.1.1 four-engine research set.

The desktop editor calls this module only after the user accepts the single
first-run offer for all four engines. The experimental installer can invoke
the same entry point when its one-time setup task is selected. No download
starts before explicit consent, and subsequent enhancement runs offline.
"""
from __future__ import annotations

import os
import queue
import stat
import threading
from pathlib import Path


_REQUIRED_ENGINES = {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}


def install_for_offline_use() -> dict:
    """Install and verify all four native engines for the current Windows user."""
    from .v211_auto_setup import provision_after_consent

    result = provision_after_consent()
    status = result.get("status")
    names = set(result.get("verified_engine_names", ()))
    if status not in {"installed_for_offline_qa", "already_installed"}:
        raise RuntimeError("four-engine setup did not reach a completed state")
    if names != _REQUIRED_ENGINES:
        raise RuntimeError("four-engine setup did not verify exactly the required engines")
    return result



_EXPECTED_RELEASES = {
    "real_esrgan": "v0.2.5.0",
    "waifu2x": "20250915",
    "real_cugan": "20220728",
    "anime4k": "v3.2.0",
}

_EXPECTED_DIGEST_FIELDS = {
    "real_esrgan": "observed_sha256",
    "waifu2x": "release_sha256",
    "real_cugan": "observed_sha256",
    "anime4k": "release_sha256",
}

_EXPECTED_LICENSE_URLS = {
    "real_esrgan": "https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/blob/master/LICENSE",
    "waifu2x": "https://github.com/nihui/waifu2x-ncnn-vulkan/blob/master/LICENSE",
    "real_cugan": "https://github.com/nihui/realcugan-ncnn-vulkan/blob/master/LICENSE",
    "anime4k": "https://github.com/TianZerL/Anime4KCPP/blob/master/LICENSE-GPLv3",
}


def preflight_v211_provisioning() -> dict:
    """Validate the frozen installer/provisioner graph without network or writes."""
    from .v211_auto_setup import selected_manifest
    from tools.v211_official_assets_audit import PACKAGES as AUDIT_PACKAGES
    from tools.v211_provision_four_engines import (
        PACKAGES as PROVISION_PACKAGES,
        ensure_verified_archive,
        provision_from_archives,
    )
    from tools.v211_real_engine_manifest import load_real_engine_manifest

    if set(AUDIT_PACKAGES) != _REQUIRED_ENGINES or set(PROVISION_PACKAGES) != _REQUIRED_ENGINES:
        raise RuntimeError("provisioner must expose exactly the four approved engines")
    if PROVISION_PACKAGES != AUDIT_PACKAGES:
        raise RuntimeError("provisioner package pins differ from the official audit")
    if not all(callable(item) for item in (
        ensure_verified_archive, provision_from_archives, load_real_engine_manifest,
        selected_manifest,
    )):
        raise RuntimeError("four-engine provisioning dependency graph is incomplete")

    digest_sources = {}
    for engine, expected_release in _EXPECTED_RELEASES.items():
        package = AUDIT_PACKAGES[engine]
        if package.get("release") != expected_release:
            raise RuntimeError(engine + ": unexpected upstream release pin")
        if not str(package.get("url", "")).startswith("https://github.com/"):
            raise RuntimeError(engine + ": upstream source URL is not official GitHub")
        if (not package.get("license")
                or package.get("license_url") != _EXPECTED_LICENSE_URLS[engine]):
            raise RuntimeError(engine + ": upstream license provenance is missing or incorrect")
        notices = package.get("additional_license_notices", [])
        if not isinstance(notices, list) or any(
            not isinstance(item, dict)
            or not str(item.get("url", "")).startswith("https://github.com/")
            or not item.get("name")
            for item in notices
        ):
            raise RuntimeError(engine + ": additional license notices are malformed")
        digest_field = _EXPECTED_DIGEST_FIELDS[engine]
        digest = package.get(digest_field)
        if (not isinstance(digest, str) or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)):
            raise RuntimeError(engine + ": required SHA256 pin is missing or malformed")
        digest_sources[engine] = digest_field

    return {
        "engines": sorted(_REQUIRED_ENGINES),
        "release_pins": dict(_EXPECTED_RELEASES),
        "digest_sources": digest_sources,
        "license_sources": dict(_EXPECTED_LICENSE_URLS),
        "network_started": False,
        "filesystem_modified": False,
    }

def completion_marker_path() -> Path:
    """Return the local-only success marker consumed by Inno Setup."""
    from .v211_auto_setup import qa_root

    return qa_root() / "setup-complete.flag"


def pending_marker_path() -> Path:
    """Return the per-attempt marker that prevents stale-success reuse."""
    return completion_marker_path().with_name("setup-pending.flag")


def _is_link_or_reparse_point(path: Path) -> bool:
    """Detect symlinks and Windows junction/reparse points without following them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def _validate_four_ai_data_root(data_root: str | Path) -> Path:
    """Accept only the dedicated per-profile LocalAppData engine-cache directory."""
    root = Path(data_root).expanduser()
    if not root.is_absolute():
        raise ValueError("four-engine cache path must be absolute")
    tail = [part.casefold() for part in root.parts[-4:]]
    if tail != ["appdata", "local", "niyomsilp", "v211-fourai-qa"]:
        raise ValueError("four-engine cache path is outside the approved LocalAppData location")

    profile = root.parents[3]
    if not profile.name or str(profile) == root.anchor:
        raise ValueError("four-engine cache profile root is invalid")
    protected_ancestors = (
        profile,
        profile / "AppData",
        profile / "AppData" / "Local",
        root.parent,
        root,
    )
    for candidate in protected_ancestors:
        if os.path.lexists(candidate) and (
            _is_link_or_reparse_point(candidate) or os.path.ismount(candidate)
        ):
            raise ValueError("four-engine cache path contains a link, reparse point, or mount")
    return root


def _remove_cache_entry_without_following_links(path: Path) -> None:
    """Remove one cache entry; never recurse through a symlink or junction."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return

    is_symlink = stat.S_ISLNK(info.st_mode)
    is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
    if is_symlink or is_reparse:
        # POSIX removes every symlink with unlink. Windows requires rmdir for
        # directory symlinks/junctions. Neither operation traverses the target.
        if os.name == "nt" and path.is_dir():
            os.rmdir(path)
        else:
            os.unlink(path)
        return

    if stat.S_ISDIR(info.st_mode):
        if os.path.ismount(path):
            raise ValueError("four-engine cache cleanup refuses to traverse a mount point")
        with os.scandir(path) as entries:
            for entry in entries:
                _remove_cache_entry_without_following_links(Path(entry.path))
        os.rmdir(path)
    else:
        os.unlink(path)


def cleanup_four_engine_assets(
    data_root: str | Path, *, confirmed: bool
) -> dict:
    """Remove only the dedicated four-engine cache after explicit uninstall consent.

    Unknown files in the parent cache directory are deliberately retained.
    A custom manifest override outside this installer-owned directory is never
    followed or deleted by this cleanup path.
    """
    if not confirmed:
        return {"status": "consent_required", "removed": False}

    root = _validate_four_ai_data_root(data_root)
    if not os.path.lexists(root):
        return {"status": "already_absent", "removed": False}
    if (_is_link_or_reparse_point(root) or os.path.ismount(root)
            or not root.is_dir()):
        raise ValueError("four-engine cache root is not a safe ordinary directory")

    removed = []
    for name in ("archives", "engines"):
        target = root / name
        if os.path.lexists(target):
            _remove_cache_entry_without_following_links(target)
            removed.append(name)

    for name in (
        "manifest.json",
        "setup-complete.flag",
        "setup-complete.flag.tmp",
        "setup-pending.flag",
        "setup-declined.flag",
        "installer-setup.log",
    ):
        target = root / name
        if os.path.lexists(target):
            _remove_cache_entry_without_following_links(target)
            removed.append(name)

    try:
        root.rmdir()
        removed.append("cache-directory")
    except OSError:
        # Preserve any unrecognized user-created files; never broaden cleanup.
        pass

    return {
        "status": "removed" if removed else "already_absent",
        "removed": bool(removed),
        "removed_entries": sorted(removed),
        "unknown_entries_preserved": os.path.isdir(root),
    }


def _log_path() -> Path:
    return completion_marker_path().with_name("installer-setup.log")


_SAFE_FAILURE_CODES = {
    "permission_denied", "missing_asset", "network_timeout", "network_error",
    "invalid_archive", "verification_failed", "filesystem_error",
    "setup_failed", "ui_unavailable",
}


def _record(message: str) -> None:
    """Persist only fixed status codes and the exact verified engine set."""
    safe_message = "FAILED setup_failed"
    if isinstance(message, str) and message.startswith("FAILED "):
        code = message[len("FAILED "):]
        if code in _SAFE_FAILURE_CODES:
            safe_message = message
    elif isinstance(message, str) and message.startswith("SUCCESS verified engines: "):
        names = message[len("SUCCESS verified engines: "):].split(",")
        if len(names) == len(_REQUIRED_ENGINES) and set(names) == _REQUIRED_ENGINES:
            safe_message = "SUCCESS verified engines: " + ",".join(sorted(_REQUIRED_ENGINES))

    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(safe_message + "\n")
    except OSError:
        # Logging must never convert a successful verified install into failure.
        pass


def safe_failure_code(exc: BaseException) -> str:
    """Map setup failures to fixed, privacy-safe codes; never expose exception text."""
    name = type(exc).__name__
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "missing_asset"
    if isinstance(exc, TimeoutError):
        return "network_timeout"
    if name in {"HTTPError", "URLError"}:
        return "network_error"
    if name == "BadZipFile":
        return "invalid_archive"
    if isinstance(exc, ValueError):
        return "verification_failed"
    if isinstance(exc, OSError):
        return "filesystem_error"
    return "setup_failed"


def _clear_completion_marker() -> Path:
    marker = completion_marker_path()
    marker.unlink(missing_ok=True)
    return marker


def _run_and_publish_success() -> dict:
    """Run all verification first; publish success and clear pending last."""
    marker = _clear_completion_marker()
    pending = pending_marker_path()
    try:
        result = install_for_offline_use()
        names = set(result.get("verified_engine_names", ()))
        if names != _REQUIRED_ENGINES:
            raise RuntimeError("four-engine completion marker requires all four verified engines")
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_name(marker.name + ".tmp")
        temporary.write_text(
            "NiyomSilp V2.1.1 four-engine setup verified\n",
            encoding="utf-8",
        )
        os.replace(temporary, marker)
        # Inno Setup created this pending marker for the current attempt.
        # If it cannot be removed, fail closed: the installer must not launch
        # the editor or report successful provisioning.
        pending.unlink(missing_ok=True)
        if pending.exists():
            raise OSError("could not clear the installer pending marker")
        _record("SUCCESS verified engines: " + ",".join(sorted(names)))
        return result
    except Exception as exc:
        marker.unlink(missing_ok=True)
        _record("FAILED " + safe_failure_code(exc))
        raise


def main(*, silent: bool = False, preflight_only: bool = False) -> int:
    """Run installer-time provisioning and return a process exit code.

    Silent installations do not create a hidden Tk window: they write a
    local setup log and return a nonzero code on any failed verification.
    """
    if preflight_only:
        # Used by the frozen Windows candidate smoke test. This path imports
        # the real setup/provisioning modules and validates exact upstream
        # version + digest pins, but never downloads or writes user files.
        try:
            preflight_v211_provisioning()
            return 0
        except Exception:
            return 1

    try:
        _clear_completion_marker()
    except Exception as exc:
        _record("FAILED " + safe_failure_code(exc))
        return 1

    if silent:
        try:
            _run_and_publish_success()
            return 0
        except Exception:
            return 1

    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception:
        _record("FAILED ui_unavailable")
        return 2

    root = tk.Tk()
    root.title("NiyomSilp Design · V2.1.1 AI Setup")
    root.geometry("500x170")
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", lambda: None)

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    label = ttk.Label(
        frame,
        text="กำลังดาวน์โหลด ตรวจสอบ และติดตั้ง AI ทั้ง 4 ตัว\n"
             "หลังติดตั้งแล้วจะใช้งานออฟไลน์ได้",
        justify="center",
    )
    label.pack(fill="x", pady=(4, 16))
    progress = ttk.Progressbar(frame, mode="indeterminate", length=440)
    progress.pack(fill="x")
    progress.start(12)

    events: queue.Queue = queue.Queue()
    exit_code = {"value": 1}

    def worker() -> None:
        try:
            events.put(("success", _run_and_publish_success()))
        except Exception as exc:
            events.put(("failure", safe_failure_code(exc)))

    def poll() -> None:
        try:
            state, payload = events.get_nowait()
        except queue.Empty:
            root.after(150, poll)
            return
        progress.stop()
        if state == "success":
            exit_code["value"] = 0
            messagebox.showinfo(
                "NiyomSilp Design · V2.1.1",
                "ติดตั้งและตรวจสอบ AI ทั้ง 4 ตัวเรียบร้อยแล้ว\n"
                "พร้อมใช้งานแบบออฟไลน์สำหรับงานวิจัย V2.1.1",
                parent=root,
            )
            root.destroy()
            return
        messagebox.showerror(
            "NiyomSilp Design · ติดตั้ง AI ไม่สำเร็จ",
            "ไม่สามารถติดตั้งและตรวจสอบ AI ทั้ง 4 ตัวได้\n"
            "V2 เดิมยังใช้งานได้ และสามารถลองติดตั้งใหม่ภายหลัง\n\n"
            + "รหัสสาเหตุ: " + str(payload),
            parent=root,
        )
        root.destroy()

    threading.Thread(target=worker, name="v211-installer-provision", daemon=True).start()
    root.after(150, poll)
    root.mainloop()
    return exit_code["value"]


if __name__ == "__main__":
    raise SystemExit(main())
