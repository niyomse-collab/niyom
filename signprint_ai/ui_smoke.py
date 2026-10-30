"""Exercise packaged Tk controls and the real selection dialog on Windows CI."""
import tempfile
from contextlib import nullcontext
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from tkinter import ttk
from .app_v2 import App, APP_NAME, APP_VERSION
from .face_module.selection import choose_faces


def run(layout_only=False):
    # The early layout check needs real Tk widgets, but no inference runtime.
    # Packaged smoke tests keep the real adapter and hardware detection.
    adapter = patch('signprint_ai.app_v2.NiyomSilpCoreAdapter') if layout_only else nullcontext()
    with adapter:
        app = App()
    app.auto_preview.set(False)
    def check_branding(widget):
        if 'text' in widget.keys():
            assert 'ARM' not in str(widget.cget('text')), 'Old engine branding is visible'
        for child in widget.winfo_children():
            check_branding(child)
    check_branding(app)
    assert app.title() == f"{APP_NAME} {APP_VERSION}", "Wrong release window title"
    assert app.face_mode_var.get() == "Recover", "Face default must be Recover for enhancement"
    # The queue must not take most of the workspace before any image is loaded.
    for geometry in ('1180x720', '1366x768', '1600x920'):
        app.geometry(geometry)
        app.update()
        print('Preview layout:', geometry, 'workspace', app.workspace_frame.winfo_height(),
              'preview', app.preview_shell.winfo_height(), 'queue', app.queue_shell.winfo_height(),
              'image', app.left_image.winfo_height(), flush=True)
        total = app.preview_shell.winfo_height() + app.queue_shell.winfo_height()
        assert abs(app.preview_shell.winfo_height() / total - .60) < .02
        assert app.left_image.winfo_height() >= 140
        assert abs(app.left_image.winfo_width()-app.right_image.winfo_width()) <= 1
    # Dragging over the fixed separator must not change the 60/40 split.
    workspace = app.workspace_frame
    initial_height = app.preview_shell.winfo_height()
    workspace.event_generate('<ButtonPress-1>', x=20, y=initial_height+4)
    workspace.event_generate('<B1-Motion>', x=20, y=initial_height-80)
    workspace.event_generate('<ButtonRelease-1>', x=20, y=initial_height-80)
    app.update()
    assert app.preview_shell.winfo_height() == initial_height
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder)/'smoke.png'
        Image.new('RGB', (200, 100), 'white').save(source)
        app.files = [source]
        app.current_index = 0
        app.update()
        app._refresh_preview_images()
        app.update()
        assert abs(app.left_image.winfo_width()-app.right_image.winfo_width()) <= 1
        assert abs(app.left_image.winfo_height()-app.right_image.winfo_height()) <= 1
        app._zoom_preview(1.25)
        assert app.viewport.zoom == 1.25
        app._actual_preview()
        assert app.viewport.actual
        app._fit_preview()
        assert not app.viewport.actual and app.viewport.zoom == 1
        for label, device in app._device_choices.items():
            app.device_var.set(label)
            assert app._settings().device == device
        if layout_only:
            app.destroy()
            return
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
