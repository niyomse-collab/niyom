"""Reject legacy HAT routing in V2.1.1; preserves accepted V2 baseline."""
import ast
from pathlib import Path


def test_no_hat_engine_active_in_v211_core_adapter():
    source = Path(__file__).resolve().parents[1] / "signprint_ai" / "niyomsil_core_adapter.py"
    code = source.read_text(encoding="utf-8")
    ast.parse(code)
    assert 'v2_hat_assist' not in code
    assert 'HATModelEngine' not in code
    assert 'HATAssistEngine' not in code
    assert 'HAT_SRx4' not in code


def test_approved_v2_baseline_remains_default():
    code = (Path(__file__).resolve().parents[1] / "signprint_ai" / "niyomsil_core_adapter.py").read_text(encoding="utf-8")
    assert 'getattr(settings, "v211_photo_model", "real_esrgan")' in code
    assert 'elif selected_model == "real_esrgan":' in code
    assert "self.engine_manager.create_engine(settings.device)" in code
    assert "self.face_module.apply(" in code
    assert "enforce_requested_face_restoration(" in code
