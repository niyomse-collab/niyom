"""Regression for optional NAFNet missing from four-AI experiment.

The NAFNet GoPro photograph deblur checkpoint is not part of the 4 native
engines; missing/bad NAFNet must not be silently auto-downloaded or passed.
"""
import ast
import inspect
from pathlib import Path

from signprint_ai import niyomsil_core_adapter as adapter_module
from signprint_ai import v211_nafnet_deblur as nafnet
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter


def _adapter(tmp_path, monkeypatch):
    v2 = tmp_path / "RealESRGAN_x4plus.pth"
    v2.write_bytes(b"fixture for presence-only V2 preflight, not a real checkpoint")
    monkeypatch.setattr(adapter_module, "model_path", lambda: v2)
    return NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)


def test_missing_optional_nafnet_does_not_disable_v2(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    missing = tmp_path / "NAFNet-GoPro-width64.pth"
    monkeypatch.setattr(nafnet, "nafnet_checkpoint_path", lambda: missing)
    assert adapter.selected_model_available("v2_nafnet_deblur") is False
    assert adapter.selected_model_available("real_esrgan") is True


def test_named_but_invalid_checkpoint_is_not_accepted(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    fake = tmp_path / "NAFNet-GoPro-width64.pth"
    fake.write_bytes(b"fake model, not permitted to run")
    monkeypatch.setattr(nafnet, "nafnet_checkpoint_path", lambda: fake)
    assert adapter.selected_model_available("v2_nafnet_deblur") is False
    assert adapter.selected_model_available("v2_nafnet_photo_only") is False
    assert adapter.selected_model_available("real_esrgan") is True


def test_optional_mode_preflight_really_calls_sha256_verifier(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    model = tmp_path / "mock-weight.pth"
    model.write_bytes(b"not real")
    monkeypatch.setattr(nafnet, "nafnet_checkpoint_path", lambda: model)
    seen = []
    monkeypatch.setattr(nafnet, "verify_nafnet_checkpoint",
                        lambda value: seen.append(Path(value)))
    assert adapter.selected_model_available("v2_nafnet_deblur") is True
    assert seen == [model]


def test_ui_asks_permission_to_switch_model_and_keeps_four_ai_separate():
    from signprint_ai.app_v2 import App
    source = inspect.getsource(App.start_processing)
    ast.parse(source.lstrip() if False else
              "class Dummy:\n" + "\n".join("    " + s for s in source.splitlines()))
    assert "messagebox.askyesno(" in source
    assert 'self.v211_photo_model_var.set("V2 Real-ESRGAN (เดิม)")' in source
    assert 'chosen_model = "real_esrgan"' in source
    assert 'if not approved:' in source
    assert 'self.pipeline.selected_model_available("real_esrgan")' in source
    assert "ระบบ AI 4 ตัวแยกจาก NAFNet" in source
