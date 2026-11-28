"""HAT remains an optional V2 Assist; standalone HAT replacement stays disabled."""
from pathlib import Path


def test_hat_assist_is_v2_primary_and_standalone_hat_remains_disabled():
    root = Path(__file__).resolve().parents[1]
    code = (root / "signprint_ai" / "niyomsil_core_adapter.py").read_text(encoding="utf-8")
    assert 'selected_model == "v2_hat_assist"' in code
    assert "HATAssistEngine(" in code
    assert "HATModelEngine(v2_engine.selected)" in code
    assert 'selected_model == "hat"' not in code
    assert 'getattr(settings, "v211_photo_model", "real_esrgan")' in code
    assert "self.face_module.apply(" in code
    assert "enforce_requested_face_restoration(" in code


def test_hat_uses_the_existing_optional_assist_selector_and_is_not_default():
    root = Path(__file__).resolve().parents[1]
    app = (root / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    assert 'tk.StringVar(value="V2 Real-ESRGAN (เดิม)")' in app
    assert "V2 + HAT Assist (ทดลอง" in app
    assert '"v2_hat_assist"' in app
    assert "ttk.Combobox(" in app
    assert "HAT Assist" in app and "SHA256" in app


def test_approved_v2_baseline_remains_default():
    code = (Path(__file__).resolve().parents[1] / "signprint_ai" / "niyomsil_core_adapter.py").read_text(encoding="utf-8")
    assert 'getattr(settings, "v211_photo_model", "real_esrgan")' in code
    assert 'elif selected_model == "real_esrgan":' in code
    assert "self.engine_manager.create_engine(settings.device)" in code
    assert "self.face_module.apply(" in code
    assert "enforce_requested_face_restoration(" in code
