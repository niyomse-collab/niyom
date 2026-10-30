"""HAT border tiles require attention-window alignment without geometry drift."""
import pytest
from signprint_ai.v211_hat_engine import _window_padding


@pytest.mark.parametrize("height,width,expected", [
    (32, 48, (0, 0, "reflect")),
    (37, 53, (11, 11, "reflect")),
    (96, 96, (0, 0, "reflect")),
    (1, 1, (15, 15, "replicate")),
    (3, 22, (13, 10, "replicate")),
    (15, 17, (1, 15, "reflect")),
])
def test_hat_tile_boundaries(height, width, expected):
    bottom, right, mode = _window_padding(height, width)
    assert (bottom, right, mode) == expected
    assert (height + bottom) % 16 == 0
    assert (width + right) % 16 == 0


@pytest.mark.parametrize("height,width,window", [(0, 2, 16), (1, 0, 16), (1, 1, 0)])
def test_reject_invalid_tile(height, width, window):
    with pytest.raises(ValueError):
        _window_padding(height, width, window)
