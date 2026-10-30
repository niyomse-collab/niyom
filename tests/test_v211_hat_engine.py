"""V2.1.1: optional HAT is a separate model, not a renamed slider."""
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image

from signprint_ai.v211_hat_engine import (
    HAT_SHA256, HAT_FILE, _downsample_4x, validate_checkpoint,
)


def test_wrong_or_missing_hat_checkpoint_fails_closed(tmp_path):
    assert len(HAT_SHA256) == 64
    assert HAT_FILE.endswith(".pth")
    with pytest.raises(FileNotFoundError, match="ไม่พบโมเดล"):
        validate_checkpoint(tmp_path / HAT_FILE)
    fake = tmp_path / HAT_FILE
    fake.write_bytes(b"fake checkpoint must never be loaded")
    with pytest.raises(RuntimeError, match="SHA256"):
        validate_checkpoint(fake)


def test_hat_4x_output_contract_and_2x_resample():
    pixels = np.zeros((40, 32, 3), dtype=np.uint8)
    pixels[:, :, 0] = 154
    np.testing.assert_array_equal(_downsample_4x(pixels, 4, 8, 10), pixels)
    smaller = _downsample_4x(pixels, 2, 8, 10)
    assert smaller.shape == (20, 16, 3)
    assert smaller.dtype == np.uint8
    with pytest.raises(RuntimeError, match="unexpected"):
        _downsample_4x(pixels, 4, 9, 10)


def test_hat_branch_does_not_instantiate_default_esrgan(monkeypatch):
    from signprint_ai import v211_hat_engine
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    selected = SimpleNamespace(name="CPU", device_id="cpu", backend="CPU")
    class Placeholder:
        def __init__(self, device):
            self.selected = device
    monkeypatch.setattr(v211_hat_engine, "HATModelEngine", Placeholder)
    def forbidden_engine(_):
        raise AssertionError("V2 ESRGAN initialized despite selecting HAT")
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        device_manager=SimpleNamespace(get_default_device=lambda: selected),
        create_engine=forbidden_engine, engine=None,
    )
    settings = SimpleNamespace(device="AUTO", v211_photo_model="hat",
                               graphic_ai=False, text_graphic_boost=0,
                               face_protection=False)
    result = adapter.create_job_engine(settings)
    assert isinstance(result, Placeholder)
    assert adapter.engine_manager.engine is result


def test_unknown_super_model_does_not_silently_use_old_core():
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(create_engine=lambda _:
                                             pytest.fail("not a fallback"))
    settings = SimpleNamespace(device="AUTO", v211_photo_model="not-installed")
    with pytest.raises(ValueError, match="unknown photo model"):
        adapter.create_job_engine(settings)
