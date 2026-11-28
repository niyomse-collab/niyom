"""GUI-free regression for rerunning the SAME image after moving a slider.

The V2.1 Tk UI previously stored only an index in _completed_indices: after a
successful first run, Process ignored the same image regardless of changed
settings. Tests call the real App.start_processing method with small stubs so
they run on headless Windows and Linux without creating a Tk window.
"""
from pathlib import Path
from types import SimpleNamespace

from signprint_ai.app_v2 import App
from signprint_ai.v21_graphics_ai import V21Settings


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeTree:
    def __init__(self):
        self.values = {"0": ["test.png", "48x48", "192x192",
                             "เสร็จแล้ว", "100%", "สำเร็จ"]}

    def exists(self, key):
        return key in self.values

    def item(self, key, field=None, **kwargs):
        if "values" in kwargs:
            self.values[key] = list(kwargs["values"])
        if field == "values":
            return tuple(self.values[key])
        return None


def fake_app(tmp_path):
    # No hardware model is loaded, and no Tk root is created.
    app = SimpleNamespace()
    path = tmp_path / "test.png"
    path.write_bytes(b"not decoded in this UI-level test")
    app.files = [path]
    app.scale_var = Var("4x")
    app.v211_photo_model_var = Var("V2 Real-ESRGAN (เดิม)")
    app.color_mode_var = Var("RGB")
    app.format_var = Var("PNG")
    app.icc_profile_path_var = Var("")
    app.output_dir_var = Var("")
    app._model_preflight_calls = []
    app.pipeline = SimpleNamespace(
        ai=SimpleNamespace(available=True),
        selected_model_available=lambda model: (
            app._model_preflight_calls.append(model) or True
        ),
    )
    app.current_settings = V21Settings(
        ai_scale=4, denoise=18, flat_smoothing=18
    )
    app._settings = lambda: app.current_settings
    app._settings_signature = App._settings_signature
    app._completed_indices = set()
    app._completed_signature = None
    app._queued_indices = set()
    app._face_reviews = {str(path): ()}
    app._face_key = lambda p: str(p)
    app._resume_after_faces = False
    app._active_settings = None
    app._scanning = []
    app._scan_faces = lambda p: app._scanning.append(p)
    app._running = False
    app._processing_active = lambda: app._running
    app._job_calls = []
    app._enqueue_jobs = lambda indices, settings: (
        app._job_calls.append(tuple(indices)) or len(indices)
    )
    app._ensure_queue_worker = lambda: None
    app._last_status = None
    app._set_status = lambda status: setattr(app, "_last_status", status)
    app.progress = {}
    app.tree = FakeTree()
    return app


def test_changed_slider_requeues_completed_image(tmp_path):
    app = fake_app(tmp_path)
    App.start_processing(app)
    assert app._job_calls == [(0,)]
    app._completed_indices.add(0)
    old_signature = app._completed_signature
    App.start_processing(app)
    assert app._job_calls[-1] == ()
    assert app._completed_indices == {0}

    app.current_settings = V21Settings(
        ai_scale=4, denoise=18, flat_smoothing=100
    )
    App.start_processing(app)
    assert app._completed_signature != old_signature
    assert app._completed_indices == set()
    assert app._job_calls[-1] == (0,)
    assert app.tree.values["0"][3] == "รอประมวลผลค่าใหม่"


def test_new_export_folder_reprocesses_even_when_sliders_unchanged(tmp_path):
    app = fake_app(tmp_path)
    App.start_processing(app)
    app._completed_indices.add(0)
    app.output_dir_var.value = str(tmp_path / "new-output")
    App.start_processing(app)
    assert app._job_calls == [(0,), (0,)]
    assert app._completed_indices == set()


def test_changes_during_active_job_never_mutate_inflight_settings(tmp_path):
    app = fake_app(tmp_path)
    App.start_processing(app)
    active_signature = app._completed_signature
    current = app._active_settings
    app._running = True
    app.current_settings = V21Settings(
        ai_scale=4, denoise=80, flat_smoothing=18
    )
    App.start_processing(app)
    assert app._job_calls == [(0,)]
    assert app._completed_signature == active_signature
    assert app._active_settings is current
    assert "รอให้เสร็จ" in app._last_status


def test_changed_dpi_scale_and_format_each_invalidate_completion(tmp_path):
    app = fake_app(tmp_path)
    App.start_processing(app)
    app._completed_indices.add(0)
    app.current_settings = V21Settings(
        ai_scale=8, denoise=18, flat_smoothing=18, dpi=300,
        export_format="TIFF"
    )
    App.start_processing(app)
    assert app._job_calls[-1] == (0,)
    assert app._completed_indices == set()


def test_start_processing_checks_selected_super_ai_backend(tmp_path):
    app = fake_app(tmp_path)
    app.v211_photo_model_var.value = "V2 + HAT Assist (Super AI ทดลอง)"
    App.start_processing(app)
    assert app._model_preflight_calls == ["v2_hat_assist"]
    assert app._job_calls == [(0,)]
