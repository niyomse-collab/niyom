"""V2.1.1 model preflight: only supported V2 model routes are selectable."""
from pathlib import Path
import pytest

from signprint_ai import niyomsil_core_adapter
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter


def test_esrgan_selected_without_legacy_hat(tmp_path, monkeypatch):
    weight = tmp_path / "RealESRGAN_x4plus.pth"
    weight.write_bytes(b"presence only, not actual inference")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: weight)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("real_esrgan") is True
    assert adapter.available is True


def test_no_esrgan_weight_means_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(niyomsil_core_adapter, "model_path",
                        lambda: tmp_path / "missing-RealESRGAN.pth")
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("real_esrgan") is False


@pytest.mark.parametrize("retired", ["hat", "v2_hat_assist"])
def test_retired_hat_models_are_rejected_even_when_weights_exist(tmp_path, monkeypatch, retired):
    weight = tmp_path / "RealESRGAN_x4plus.pth"
    weight.write_bytes(b"presence only")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: weight)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    with pytest.raises(ValueError, match="unknown photo model"):
        adapter.selected_model_available(retired)


def test_unknown_backend_never_falls_back():
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    with pytest.raises(ValueError, match="unknown photo model"):
        adapter.selected_model_available("other")


def test_ui_preflight_uses_selected_backend():
    from signprint_ai.app_v2 import App
    import inspect
    source = inspect.getsource(App.start_processing)
    assert "self.pipeline.selected_model_available(chosen_model)" in source
    assert "self.pipeline.ai.available" not in source
