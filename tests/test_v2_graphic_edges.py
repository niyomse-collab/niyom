"""V2-only edge refinement safeguards."""
import numpy as np
from PIL import Image

from signprint_ai.v2_graphic_edges import refine_sign_edges


def test_alpha_is_pixel_identical_after_refinement():
    arr = np.zeros((48, 72, 4), dtype=np.uint8)
    arr[:, :, :3] = (180, 20, 20)
    arr[12:36, 20:52, :3] = (245, 240, 120)
    arr[12:36, 20:52, 3] = 255
    arr[12, 20, 3] = 80
    original = Image.fromarray(arr, "RGBA")
    output = refine_sign_edges(original)
    assert output.mode == "RGBA"
    assert np.array_equal(np.asarray(output.getchannel("A")), arr[..., 3])


def test_uniform_background_unchanged():
    original = Image.new("RGB", (80, 60), (170, 15, 20))
    output = refine_sign_edges(original)
    assert output.tobytes() == original.tobytes()


def test_refinement_has_bounded_pixel_changes():
    arr = np.zeros((64, 80, 3), dtype=np.uint8)
    arr[:] = (180, 20, 20)
    arr[14:50, 18:62] = (255, 244, 120)
    original = Image.fromarray(arr, "RGB")
    result = np.asarray(refine_sign_edges(original)).astype(np.int16)
    assert np.max(np.abs(result - arr.astype(np.int16))) <= 15
