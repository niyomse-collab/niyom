"""Windows-only end-to-end construction checks for NiyomSilp Core TEST GUI.

Checks actual Tk widgets and separate naming without importing legacy ARM AI.
Real AI inference happens in the packaged EXE build, not this fast smoke test.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("NiyomSilp Independent GUI smoke requires Windows")
    import tkinter as tk
    from tkinter import ttk
    from independent_core.gui_test import TestApp
    from signprint_ai.processing import EnhanceSettings

    app = TestApp()
    try:
        app.update()
        assert "Core TEST" in app.title(), app.title()
        assert app.hardware_info["engine"] == "NiyomSilp Core TEST"
        assert app.pipeline.__class__.__name__ == "DesktopTestAdapter"
        assert app.winfo_exists() and app.tree is not None
        controls = []

        def descend(w):
            if isinstance(w, (ttk.Button, tk.Button)):
                controls.append((w.cget("text"), w.cget("command")))
            for child in w.winfo_children():
                descend(child)

        descend(app)
        active = {label for label, callback in controls if callback}
        expected = {"เปิดไฟล์", "ประมวลผล", "บันทึก", "เพิ่มไฟล์",
                    "ลบที่เลือก", "หยุดการทำงาน", "เลือก ICC…", "เลือกโฟลเดอร์"}
        missing = expected - active
        assert not missing, f"Buttons missing their callbacks: {missing}"

        # Verify the test version never proposes the production _Niyomsil_AI filename.
        base = Path("C:/QA-sample/original.png")
        app.output_dir_var.set("C:/QA-output")
        settings = EnhanceSettings(export_format="PNG", color_mode="RGB")
        test_result = app._output_path(base, settings)
        assert test_result.name == "original_NiyomSilp_CoreTEST.png", test_result.name
        assert "_Niyomsil_AI" not in test_result.name

        app.original_ratio = 2.0
        app.lock_ratio.set(True)
        app.width_var.set("120")
        app._size_edited("w")
        assert abs(float(app.height_var.get()) - 60) < 0.001
        app.stop_processing()
        assert app._stop.is_set()
        print(f"NIYOMSIL_INDEPENDENT_UI_PASS: {len(active)} buttons; ratio and safe output names OK")
    finally:
        app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
