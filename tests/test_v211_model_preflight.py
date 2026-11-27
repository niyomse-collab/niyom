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


def test_standalone_hat_model_remains_rejected(tmp_path, monkeypatch):
    weight = tmp_path / "RealESRGAN_x4plus.pth"
    weight.write_bytes(b"presence only")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: weight)
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    with pytest.raises(ValueError, match="unknown photo model"):
        adapter.selected_model_available("hat")


def test_v2_hat_assist_requires_verified_checkpoint_and_spandrel(tmp_path, monkeypatch):
    import sys
    from types import ModuleType
    from signprint_ai import v211_hat_engine

    base = tmp_path / "RealESRGAN_x4plus.pth"
    checkpoint = tmp_path / "HAT_SRx4_ImageNet-pretrain.pth"
    base.write_bytes(b"presence only")
    checkpoint.write_bytes(b"synthetic checkpoint placeholder")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: base)
    monkeypatch.setattr(v211_hat_engine, "checkpoint_path", lambda: checkpoint)
    monkeypatch.setattr(v211_hat_engine, "validate_checkpoint", lambda path: None)

    spandrel = ModuleType("spandrel")
    spandrel.ImageModelDescriptor = object
    spandrel.ModelLoader = object
    monkeypatch.setitem(sys.modules, "spandrel", spandrel)

    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("v2_hat_assist") is True

    monkeypatch.delitem(sys.modules, "spandrel")
    assert adapter.selected_model_available("v2_hat_assist") is False


def test_v2_hat_assist_fails_closed_on_checkpoint_hash_error(tmp_path, monkeypatch):
    from signprint_ai import v211_hat_engine

    base = tmp_path / "RealESRGAN_x4plus.pth"
    base.write_bytes(b"presence only")
    monkeypatch.setattr(niyomsil_core_adapter, "model_path", lambda: base)
    monkeypatch.setattr(v211_hat_engine, "checkpoint_path", lambda: tmp_path / "bad.pth")
    monkeypatch.setattr(
        v211_hat_engine, "validate_checkpoint",
        lambda path: (_ for _ in ()).throw(RuntimeError("SHA256 mismatch")),
    )
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    assert adapter.selected_model_available("v2_hat_assist") is False


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
