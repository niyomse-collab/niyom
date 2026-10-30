"""V2.1.1 selected-model preflight: HAT must not require duplicate V2 weights."""
from pathlib import Path

import pytest

from signprint_ai import niyomsil_core_adapter, v211_hat_engine
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter


def test_hat_selected_with_no_esrgan_weight(tmp_path, monkeypatch):
    hat = tmp_path / "HAT.pth"
    hat.write_bytes(b"test stub: presence only, not production weights")
    monkeypatch.setattr(v211_hat_engine, "checkpoint_path", lambda: hat)
    monkeypatch.setattr(niyomsil_core_adapter, "model_path",
                        lambda: tmp_path / "missing-ESRGAN.pth")
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.available is False
    assert adapter.selected_model_available("hat") is True
    assert adapter.selected_model_available("real_esrgan") is False


def test_esrgan_selected_without_hat_weight(tmp_path, monkeypatch):
    esrgan = tmp_path / "RealESRGAN_x4plus.pth"
    esrgan.write_bytes(b"test stub: presence only")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: esrgan)
    monkeypatch.setattr(v211_hat_engine, "checkpoint_path",
                        lambda: tmp_path / "missing-HAT.pth")
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("hat") is False
    assert adapter.selected_model_available("real_esrgan") is True


def test_unknown_backend_never_falls_back(tmp_path):
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    with pytest.raises(ValueError, match="unknown photo model"):
        adapter.selected_model_available("other")


def test_ui_preflight_uses_selected_backend():
    from signprint_ai.app_v2 import App
    import inspect

    source = inspect.getsource(App.start_processing)
    assert "self.pipeline.selected_model_available(chosen_model)" in source
    assert "self.pipeline.ai.available" not in source
