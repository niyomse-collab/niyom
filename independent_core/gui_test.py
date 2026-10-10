"""Start the original NiyomSilp desktop UI with independent TEST backend.

No edits to signprint_ai/app_v2.py; the GUI layout and its callbacks are reused.
An obvious TEST title and independent output names prevent confusion/overwrites.
"""
from __future__ import annotations

import tkinter as tk
import sys
import types
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from independent_core.desktop_adapter import DesktopTestAdapter
from independent_core.icc_library import list_external_profiles

# Prevent importing/packaging the ARM application engine. The unchanged GUI
# only needs a class with the same constructor and processing contract.
compat = types.ModuleType("signprint_ai.arm_core_adapter")
compat.ARMCoreAdapter = DesktopTestAdapter
sys.modules["signprint_ai.arm_core_adapter"] = compat
import signprint_ai.app_v2 as original

original.ARMCoreAdapter = DesktopTestAdapter
original.APP_NAME = "NiyomSilp Design — Independent Core TEST"
original.APP_VERSION = "EXPERIMENT — Not the stable installer"


class TestApp(original.App):
    def __init__(self):
        super().__init__()
        self.title("นิยมศิลป์ดีไซน์ — NiyomSilp Independent Core TEST")
        self._set_status("โหมดทดลองแยกจากโปรแกรมหลัก • ไม่เขียนทับไฟล์เดิม")

    def _detect_hardware(self):
        info = super()._detect_hardware()
        info["engine"] = "NiyomSilp Core TEST"
        return info

    def _build_ui(self):
        super()._build_ui()
        self._mark_test_strings(self)

    def _mark_test_strings(self, widget):
        # Only edit the wording that wrongly identifies the AI core as ARM.
        try:
            text = str(widget.cget("text"))
            if "ARM V2.2.8" in text:
                widget.configure(text=text.replace("ARM V2.2.8", "NiyomSilp Core TEST"))
            elif "ผลลัพธ์ ARM Core" in text:
                widget.configure(text=text.replace("ผลลัพธ์ ARM Core", "ผลลัพธ์ NiyomSilp TEST"))
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._mark_test_strings(child)

    def _output_path(self, src: Path, settings):
        # Never share original GUI's fixed _Niyomsil_AI naming namespace.
        ext = {"PNG": ".png", "TIFF": ".tif", "PDF": ".pdf", "JPG": ".jpg"}[settings.export_format]
        base = Path(self.output_dir_var.get()) if self.output_dir_var.get() else src.parent
        mode = "_CMYK" if settings.color_mode.upper() == "CMYK" else ""
        stem = f"{src.stem}_NiyomSilp_CoreTEST{mode}"
        dest = base / f"{stem}{ext}"
        version = 2
        used_in_queue = {
            row[2] for row in list(self._job_queue.queue)
        }
        while dest.exists() or dest in used_in_queue:
            dest = base / f"{stem}_{version}{ext}"
            version += 1
        return dest

    def _choose_icc_profile(self):
        selected = filedialog.askopenfilename(
            title="เลือก ICC, ICM หรือ ZIP โปรไฟล์ (Core TEST)",
            filetypes=[
                ("ICC / ICM / ZIP", "*.icc;*.icm;*.zip"),
                ("ZIP profiles", "*.zip"),
                ("ICC/ICM profiles", "*.icc;*.icm"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        if not selected.lower().endswith(".zip"):
            self.pipeline.zip_icc_sha256 = None
            self.icc_profile_path_var.set(selected)
            self.icc_profile_name_var.set(Path(selected).name)
            self._settings_changed(schedule_preview=False)
            return
        try:
            choices = [
                item for item in list_external_profiles(selected)
                if item.color_space == "CMYK" and item.device_class == "prtr"
            ]
        except Exception as exc:
            messagebox.showerror("ICC TEST", str(exc), parent=self)
            return
        if not choices:
            messagebox.showerror("ICC TEST", "ไม่พบโปรไฟล์ CMYK Printer ใน ZIP", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("เลือก ICC จาก ZIP — NiyomSilp Core TEST")
        dialog.geometry("680x155")
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="เลือกโปรไฟล์ CMYK ที่ต้องการทดลอง (ไม่ใช่การสอบเทียบเครื่องพิมพ์)", font=("Tahoma", 10)).pack(padx=10, pady=12)
        descriptions = [f"{item.description} | {item.filename} | {item.sha256[:12]}" for item in choices]
        picked = tk.StringVar(value=descriptions[0])
        selector = ttk.Combobox(dialog, textvariable=picked, values=descriptions,
                                state="readonly", width=85)
        selector.pack(fill="x", padx=14, pady=(0, 12))

        def confirm():
            i = descriptions.index(picked.get())
            item = choices[i]
            self.pipeline.zip_icc_sha256 = item.sha256
            self.icc_profile_path_var.set(selected)
            self.icc_profile_name_var.set(item.description)
            self._settings_changed(schedule_preview=False)
            dialog.destroy()

        ttk.Button(dialog, text="ยืนยัน ICC ที่เลือก", command=confirm).pack(padx=10)

    def start_processing(self):
        if self.color_mode_var.get() == "CMYK":
            name = self.icc_profile_path_var.get().strip()
            if name.lower().endswith(".zip") and not self.pipeline.zip_icc_sha256:
                messagebox.showerror("NiyomSilp Core TEST", "ต้องเลือก ICC ใน ZIP ก่อนเริ่มประมวลผล")
                return
        return super().start_processing()


def main():
    TestApp().mainloop()


if __name__ == "__main__":
    main()
