"""Installer-time provisioning entry point for the V2.1.1 four-engine research set.

The desktop editor itself never downloads models or asks setup questions on
launch. The experimental installer invokes this module only when the user
selects the one-time four-engine setup task.
"""
from __future__ import annotations

import os
import queue
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


def completion_marker_path() -> Path:
    """Return the local-only success marker consumed by Inno Setup."""
    from .v211_auto_setup import qa_root

    return qa_root() / "setup-complete.flag"


def pending_marker_path() -> Path:
    """Return the per-attempt marker that prevents stale-success reuse."""
    return completion_marker_path().with_name("setup-pending.flag")


def _log_path() -> Path:
    return completion_marker_path().with_name("installer-setup.log")


def _record(message: str) -> None:
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(message.replace("\r", " ").replace("\n", " ") + "\n")
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


def main(*, silent: bool = False) -> int:
    """Run installer-time provisioning and return a process exit code.

    Silent installations do not create a hidden Tk window: they write a
    local setup log and return a nonzero code on any failed verification.
    """
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
