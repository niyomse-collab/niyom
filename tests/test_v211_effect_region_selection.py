import math

import pytest

from signprint_ai.effect_region_selection import normalized_drag_rectangle
from signprint_ai.v21_graphics_ai import V21Settings


def test_drag_rectangle_normalizes_reverse_direction():
    assert normalized_drag_rectangle(
        (80, 60), (20, 10), (100, 80)
    ) == (0.2, 0.125, 0.8, 0.75)


def test_drag_rectangle_clamps_to_image_bounds():
    assert normalized_drag_rectangle(
        (-20, -5), (120, 65), (100, 60)
    ) == (0.0, 0.0, 1.0, 1.0)


def test_drag_rectangle_ignores_clicks_and_tiny_drags():
    assert normalized_drag_rectangle((10, 10), (10, 10), (100, 80)) is None
    assert normalized_drag_rectangle((10, 10), (12, 30), (100, 80)) is None
    assert normalized_drag_rectangle((10, 10), (30, 12), (100, 80)) is None


@pytest.mark.parametrize(
    "start,end,size",
    [
        ((0, 0), (10, 10), (0, 80)),
        ((0, 0), (10, 10), (100, -1)),
        ((0,), (10, 10), (100, 80)),
        ((0, 0), (10, 10), (100,)),
        ((0, 0), (math.nan, 10), (100, 80)),
        ((0, 0), (10, math.inf), (100, 80)),
        ((False, 0), (10, 10), (100, 80)),
    ],
)
def test_drag_rectangle_rejects_invalid_geometry(start, end, size):
    with pytest.raises(ValueError):
        normalized_drag_rectangle(start, end, size)


def test_v21_settings_exposes_per_file_styled_effect_protection():
    settings = V21Settings()
    assert settings.v211_protected_effect_regions == ()
    protected = ((0.1, 0.2, 0.8, 0.9),)
    from dataclasses import replace

    updated = replace(settings, v211_protected_effect_regions=protected)
    assert updated.v211_protected_effect_regions == protected
