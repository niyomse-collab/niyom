"""Regression checks for independent width/height printing (no white padding)."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


@pytest.mark.parametrize("width,height", [(120, 40), (60, 100), (100, 100), (20, 160)])
def test_free_size_stretches_image_to_all_four_edges(monkeypatch, tmp_path, width, height):
    from signprint_ai import independent_core
    from signprint_ai.independent_core import DeviceInfo
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.processing import EnhanceSettings

    monkeypatch.setattr(independent_core, "DeviceManager", lambda: SimpleNamespace(
        get_default_device=lambda: DeviceInfo("cpu", "CPU", "CPU")
    ))
    src = tmp_path / "input.png"
    dst = tmp_path / "result.png"
    original_color = (41, 123, 207)
    Image.new("RGB", (60, 40), original_color).save(src)

    settings = EnhanceSettings(
        print_width=width, print_height=height,
        print_unit="inch", dpi=1, resize_mode="stretch",
    )
    NiyomSilpCoreAdapter().process(src, dst, settings, use_ai=False)
    with Image.open(dst) as result:
        assert result.size == (width, height)
        # Solid colored pixels must reach every edge and corner.
        border_points = [
            (0, 0), (width - 1, 0), (0, height - 1),
            (width - 1, height - 1), (width // 2, 0),
            (width // 2, height - 1), (0, height // 2),
            (width - 1, height // 2),
        ]
        assert all(result.getpixel(point) == original_color for point in border_points)


def test_ratio_lock_checkbox_recomputes_on_click():
    from signprint_ai.app_v2 import App

    events = []
    fake = SimpleNamespace(
        lock_ratio=SimpleNamespace(get=lambda: True),
        _size_edited=lambda side: events.append(("sync", side)),
        _settings_changed=lambda: events.append(("refresh",)),
    )
    App._ratio_lock_changed(fake)
    assert events == [("sync", "w")]

    events.clear()
    fake.lock_ratio = SimpleNamespace(get=lambda: False)
    App._ratio_lock_changed(fake)
    assert events == [("refresh",)]


def test_screen_explains_unlock_stretch():
    source = (Path(__file__).resolve().parents[1] / "signprint_ai" / "app_v2.py").read_text("utf-8")
    assert "command=self._ratio_lock_changed" in source
    assert "ยืดหรือหดภาพเต็มพื้นที่ ไม่มีขอบขาว" in source
