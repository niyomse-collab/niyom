"""Exercise packaged Tk controls and the real selection dialog on Windows CI."""
import tempfile
from pathlib import Path
from PIL import Image
from tkinter import ttk
from .app_v2 import App
from .face_module.selection import choose_faces


def run():
    app = App()
    app.auto_preview.set(False)
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder)/'smoke.png'
        Image.new('RGB', (200, 100), 'white').save(source)
        app.files = [source]
        app.current_index = 0
        app.update()
        app._refresh_preview_images()
        app._zoom_preview(1.25)
        assert app.viewport.zoom == 1.25
        app._actual_preview()
        assert app.viewport.actual
        app._fit_preview()
        assert not app.viewport.actual and app.viewport.zoom == 1
        for label, device in app._device_choices.items():
            app.device_var.set(label)
            assert app._settings().device == device
        regions = ((.1,.1,.4,.6), (.6,.1,.9,.6))
        def confirm():
            def visit(widget):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget('text') == 'ยืนยันใบหน้าที่เลือก':
                        child.invoke()
                        return True
                    if visit(child):
                        return True
                return False
            assert visit(app), 'Face confirmation button is missing'
        app.after(300, confirm)
        assert choose_faces(app, source, regions) == regions
        # Initialize and run the actual packaged RetinaFace detector on a blank image.
        # This proves model execution/imports, not recognition accuracy on portraits.
        import torch
        torch.set_num_threads(2)
        assert app._face_detector.detect(source) == ()
    app.destroy()
