"""Windows-only widget and control smoke for the UNMODIFIED NiyomSilp UI.

This builds the real Tk UI but stubs the unneeded heavy ARM *inference import*
for a quick GUI test. It does not pretend to test AI rendering or save dialogs.
"""
from __future__ import annotations
import os
import sys
import types
from pathlib import Path


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("Windows UI smoke requires a Windows machine")
    import tkinter as tk
    from tkinter import ttk

    stub = types.ModuleType("signprint_ai.arm_core_adapter")

    class ARMCoreAdapter:
        def __init__(self):
            self.ai = types.SimpleNamespace(available=False)

        def default_device(self):
            return types.SimpleNamespace(name="CPU smoke test", backend="cpu", memory_mb=0)

    stub.ARMCoreAdapter = ARMCoreAdapter
    sys.modules["signprint_ai.arm_core_adapter"] = stub

    # Script entrypoints add tools/ (not the repository root) to sys.path on Windows.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from signprint_ai.app_v2 import App
    window = App()
    try:
        window.update()
        assert "Niyomsil" in window.title(), window.title()
        assert window.winfo_exists()
        assert window.tree is not None
        assert window.progress is not None

        buttons = []
        def visit(widget):
            if isinstance(widget, (tk.Button, ttk.Button)):
                buttons.append((widget.cget("text"), widget.cget("command")))
            for child in widget.winfo_children():
                visit(child)
        visit(window)

        # Require handlers to actually be attached to UI widgets.
        expected = ("เปิดไฟล์", "ประมวลผล", "บันทึก",
                    "เพิ่มไฟล์", "ลบที่เลือก", "หยุดการทำงาน",
                    "เลือกโฟลเดอร์", "เลือก ICC…", "1:1")
        labels = {text for text, command in buttons if command}
        missing = [name for name in expected if name not in labels]
        assert not missing, f"Missing/broken button bindings: {missing}"

        # Exercise real control plumbing without invoking dialogs / GPU.
        window.original_ratio = 2.0
        window.lock_ratio.set(True)
        window.width_var.set("120")
        window._size_edited("w")
        assert abs(float(window.height_var.get()) - 60) < 1e-7

        window.use_print_size.set(True)
        window.dpi_var.set("300")
        window.format_var.set("TIFF")
        window.color_mode_var.set("RGB")
        config = window._settings()
        assert config.print_width == 120.0
        assert config.print_height == 60.0
        assert config.dpi == 300
        assert config.export_format == "TIFF"
        assert config.color_mode == "RGB"

        path = window._output_path(Path("sample.png"), config)
        assert path.suffix == ".tif", path
        window.stop_processing()
        assert window._stop.is_set()
        assert window.status_label.cget("text") != ""
        print(f"WINDOWS_UI_SMOKE_PASS: {len(buttons)} bound candidates; controls and sizing OK")
        return 0
    finally:
        window.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
