"""Installer-time provisioning entry point for the V2.1.1 four-engine research set.

The desktop editor itself never downloads models or asks setup questions on
launch. The experimental installer invokes this module only when the user
selects the one-time four-engine setup task.
"""
from __future__ import annotations

import queue
import threading


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


def main() -> int:
    """Show a small installer-time progress window and return a process code."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception:
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

    def worker() -> None:
        try:
            events.put(("success", install_for_offline_use()))
        except Exception as exc:
            events.put(("failure", exc))

    def poll() -> None:
        try:
            state, payload = events.get_nowait()
        except queue.Empty:
            root.after(150, poll)
            return
        progress.stop()
        if state == "success":
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
            + type(payload).__name__ + ": " + str(payload),
            parent=root,
        )
        root.destroy()

    threading.Thread(target=worker, name="v211-installer-provision", daemon=True).start()
    root.after(150, poll)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
