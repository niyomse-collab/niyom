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


def test_blurred_navy_lettering_edge_is_cleaner_without_erasing_small_marks():
    """A synthetic Thai-like detached mark and a blue stroke on cream."""
    import cv2

    rng = np.random.default_rng(12)
    clean = np.zeros((192, 256, 3), dtype=np.uint8)
    clean[:] = (245, 230, 178)
    clean[54:136, 40:210] = (28, 47, 126)
    clean[35:44, 80:95] = (28, 47, 126)  # detached tone mark
    clean = cv2.GaussianBlur(clean, (0, 0), 0.68)
    noise = rng.integers(-9, 10, clean.shape, dtype=np.int16)
    damaged = np.clip(clean.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    result = np.asarray(refine_sign_edges(Image.fromarray(damaged, "RGB")))
    edge = (slice(65, 124), slice(42, 47))
    before = np.abs(damaged[edge].astype(np.int16) - clean[edge].astype(np.int16)).mean()
    after = np.abs(result[edge].astype(np.int16) - clean[edge].astype(np.int16)).mean()
    assert after < before * 0.8
    # No new hue extrema, enlarged strokes, or loss of a detached tone mark.
    assert np.max(np.abs(result.astype(np.int16) - damaged.astype(np.int16))) <= 15
    assert result[39, 85, 2] > result[39, 85, 0]
    assert result[26, 85, 0] > result[26, 85, 2]


def test_selected_face_rectangle_is_pixel_identical():
    import cv2

    rgb = np.empty((160, 224, 3), dtype=np.uint8)
    rgb[:] = (250, 226, 180)
    rgb[34:127, 18:202] = (20, 40, 125)
    rgb = cv2.GaussianBlur(rgb, (0, 0), 0.9)
    img = Image.fromarray(rgb, "RGB")
    protected = ((0.5, 0.15, 0.9, 0.85),)
    out = np.asarray(refine_sign_edges(img, protected_regions=protected))
    # The face and its margin must never be sharpened or recolored.
    np.testing.assert_array_equal(out[24:136, 112:202], rgb[24:136, 112:202])
    assert np.any(out[40:110, 17:26] != rgb[40:110, 17:26])


def test_padded_tile_matches_whole_image_refinement():
    import cv2

    rng = np.random.default_rng(5)
    rgb = np.zeros((192, 192, 3), dtype=np.uint8)
    rgb[:] = (242, 221, 171)
    rgb[36:180, 34:165] = (29, 45, 121)
    rgb = cv2.GaussianBlur(rgb, (0, 0), 0.7)
    rgb = np.clip(rgb.astype(np.int16) + rng.integers(-3, 4, rgb.shape),
                  0, 255).astype(np.uint8)
    whole = np.asarray(refine_sign_edges(Image.fromarray(rgb, "RGB")))
    pad, lo, hi = 26, 64, 128
    padded = np.asarray(refine_sign_edges(Image.fromarray(
        rgb[lo-pad:hi+pad, lo-pad:hi+pad], "RGB"
    )))
    np.testing.assert_allclose(
        whole[lo:hi, lo:hi], padded[pad:-pad, pad:-pad], atol=1
    )
