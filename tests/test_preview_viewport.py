import numpy as np
from PIL import Image
from signprint_ai.preview_viewport import PreviewViewport


def test_fit_zoom_and_actual_pixels():
    view = PreviewViewport()
    assert view.scale((1000, 500), (200, 200)) == .2
    view.magnify(2)
    assert view.scale((1000, 500), (200, 200)) == .4
    view.one_to_one()
    assert view.scale((1000, 500), (200, 200)) == 1
    view.fit()
    assert (view.zoom, view.actual, view.center_x, view.center_y) == (1, False, .5, .5)


def test_pan_shared_coordinates_and_bounds():
    view = PreviewViewport(zoom=2)
    view.pan(20, -10, (1000, 500), (200, 200))
    assert (view.center_x, view.center_y) == (.45, .55)
    # Same normalized coordinate lands on corresponding Before/After detail.
    assert view.center_x*2000 == 900
    view.pan(100000, -100000, (1000, 500), (200, 200))
    assert (view.center_x, view.center_y) == (0, 1)


def test_one_to_one_crop_and_bounded_render():
    pixels = np.zeros((100, 200, 3), dtype=np.uint8)
    pixels[:, :, 0] = np.arange(200)
    image = Image.fromarray(pixels)
    view = PreviewViewport(actual=True)
    rendered = view.render(image, (20, 20))
    assert rendered.size == (20, 20)
    np.testing.assert_array_equal(np.asarray(rendered), pixels[40:60, 90:110])
    view.magnify(64)
    assert view.render(image, (20, 20)).size == (20, 20)


def test_one_to_one_uses_common_output_scale():
    view = PreviewViewport(actual=True)
    reference = (2000, 1000)
    assert view.scale((1000,500),(500,300),reference) == 2
    assert view.scale((2000,1000),(500,300),reference) == 1
    view.pan(100,0,(1000,500),(500,300),reference)
    center = view.center_x
    view.center_x = .5
    view.pan(100,0,(2000,1000),(500,300),reference)
    assert view.center_x == center
