"""GitHub Actions real-inference experiment for a separate HAT checkpoint.

This only proves execution and dimensions with a synthetic RGB crop.
It does not certify image quality, customer artwork, model rights, or print.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageCms

from signprint_ai.v211_hat_engine import HATModelEngine, checkpoint_path, validate_checkpoint


def main():
    model = checkpoint_path()
    validate_checkpoint(model)
    selector = SimpleNamespace(device_id="cpu", backend="CPU", name="CPU")
    engine = HATModelEngine(selector)
    height, width = 32, 48
    yy, xx = np.mgrid[:height, :width]
    source = np.dstack((
        np.clip(8 + 5 * xx, 0, 255),
        np.clip(5 + 7 * yy, 0, 255),
        (xx % 9) * 27,
    )).astype("uint8")
    crop = engine.enhance_tile(source, scale=4)
    if crop.shape != (height * 4, width * 4, 3):
        raise AssertionError("HAT real inference returned unexpected size")
    if not crop.std() > 1:
        raise AssertionError("HAT output collapsed to a flat image")
    # Exercise actual model execution on non-window-aligned and tiny border
    # crops. Unit tests alone cannot prove that the pretrained model accepts
    # reflect/replicate padding and correctly crops 2x/4x predictions.
    boundary_cases = []
    for case_name, case_height, case_width, case_scale in (
        ("odd_4x", 17, 19, 4),
        ("tiny_4x", 1, 1, 4),
        ("odd_2x", 17, 19, 2),
    ):
        yy2, xx2 = np.mgrid[:case_height, :case_width]
        sample = np.dstack((
            (xx2 * 11 + 7) % 256,
            (yy2 * 13 + 3) % 256,
            (xx2 * 5 + yy2 * 7) % 256,
        )).astype("uint8")
        actual = engine.enhance_tile(sample, scale=case_scale)
        expected = (case_height * case_scale, case_width * case_scale, 3)
        if actual.shape != expected or not np.isfinite(actual).all():
            raise AssertionError(f"{case_name}: bad output {actual.shape} != {expected}")
        boundary_cases.append({
            "case": case_name, "input_size": [case_width, case_height],
            "output_size": [actual.shape[1], actual.shape[0]],
            "output_std": float(actual.std()),
        })

    output_dir = Path("hat-inference-proof")
    output_dir.mkdir(exist_ok=True)

    # Force the actual file-based HAT path to cross several padded tile
    # boundaries; this is an execution check, not a seam-quality approval.
    with TemporaryDirectory(prefix="hat-v211-proof-") as temporary:
        input_file = Path(temporary) / "input.png"
        output_file = Path(temporary) / "output.png"
        hh, ww = 25, 50
        ty, tx = np.mgrid[:hh, :ww]
        tiled_source = np.dstack((
            (tx * 3 + 40) % 256,
            (ty * 5 + 20) % 256,
            (tx * 2 + ty * 3) % 256,
        )).astype("uint8")
        Image.fromarray(tiled_source, "RGB").save(input_file)
        engine.upsampler.tile_size = 24
        engine.upsampler.tile_pad = 16
        tiled_result = engine.enhance(input_file, output_file, scale=2)
        with Image.open(output_file) as tiled_output:
            if tiled_output.size != (ww * 2, hh * 2):
                raise AssertionError("HAT file-based tiled output has wrong size")
            tiled_pixels = np.asarray(tiled_output).copy()
            tiled_std = float(tiled_pixels.std())
        if tiled_result["tiles"] <= 1 or tiled_std <= 1:
            raise AssertionError("HAT did not perform meaningful multi-tile inference")

        # Compare the actual multi-tile model output with a single full-frame
        # pass. Record seam error; a passing execution is NOT a visual QA pass.
        full_pixels = engine.enhance_tile(tiled_source, scale=2)
        if full_pixels.shape != tiled_pixels.shape:
            raise AssertionError("HAT full/tiled comparison dimensions differ")
        difference = np.abs(
            tiled_pixels.astype(np.int16) - full_pixels.astype(np.int16)
        )
        seam_mask = np.zeros((hh * 2, ww * 2), dtype=bool)
        for x in range(24 * 2, ww * 2, 24 * 2):
            seam_mask[:, max(0, x - 2):min(ww * 2, x + 2)] = True
        for y in range(24 * 2, hh * 2, 24 * 2):
            seam_mask[max(0, y - 2):min(hh * 2, y + 2), :] = True
        if not seam_mask.any():
            raise AssertionError("HAT seam diagnostic mask was empty")
        seam_diagnostic = {
            "seam_mean_abs_error": float(difference[seam_mask].mean()),
            "seam_max_abs_error": int(difference[seam_mask].max()),
            "full_image_mean_abs_error": float(difference.mean()),
            "comparison": "same source, same output pixels; full HAT vs tiled HAT",
            "quality_certified": False,
        }

        # Actual checkpoint inference through the RGBA file export path.
        # This catches missing cv2, alpha flattening and ICC/DPI loss that
        # synthetic stub-engine regressions alone cannot detect.
        rgba_input = Path(temporary) / "input_rgba.png"
        rgba_output = output_dir / "HAT_x2_rgba_synthetic.png"
        rgba = np.zeros((11, 13, 4), dtype=np.uint8)
        rgba[2:9, 3:10, :3] = (210, 65, 20)
        rgba[2:9, 3:10, 3] = 255
        rgba[2:9, 3, 3] = 128
        rgba[2:9, 9, 3] = 64
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        Image.fromarray(rgba, "RGBA").save(
            rgba_input, dpi=(300, 300), icc_profile=icc
        )
        rgba_result = engine.enhance(rgba_input, rgba_output, scale=2)
        with Image.open(rgba_output) as actual:
            expected_alpha = Image.fromarray(rgba[:, :, 3], "L").resize(
                (26, 22), Image.Resampling.LANCZOS
            )
            if actual.mode != "RGBA" or actual.size != (26, 22):
                raise AssertionError("Real HAT RGBA output lost mode/dimensions")
            if actual.getchannel("A").tobytes() != expected_alpha.tobytes():
                raise AssertionError("Real HAT RGBA output changed alpha values")
            if actual.info.get("icc_profile") != icc:
                raise AssertionError("Real HAT RGBA output lost the sRGB ICC")
            actual_dpi = actual.info.get("dpi")
            if not actual_dpi or any(abs(v - 300) > 1 for v in actual_dpi):
                raise AssertionError("Real HAT RGBA output lost 300 DPI")
            rgba_diagnostic = {
                "mode": actual.mode,
                "output_size": list(actual.size),
                "alpha_extrema": list(actual.getchannel("A").getextrema()),
                "icc_preserved": True,
                "dpi": list(actual_dpi),
                "model": rgba_result["model"],
                "quality_certified": False,
            }

    Image.fromarray(crop, "RGB").save(output_dir / "HAT_x4_synthetic.png")
    details = {
        "model": model.name,
        "checksum_verified": True,
        "backend": "CPU",
        "input_size": [width, height],
        "output_size": [crop.shape[1], crop.shape[0]],
        "output_std": float(crop.std()),
        "boundary_cases": boundary_cases,
        "tiled_file_inference": {
            "tiles": tiled_result["tiles"],
            "output_size": [ww * 2, hh * 2],
            "output_std": tiled_std,
        },
        "full_vs_tiled_seam_diagnostic": seam_diagnostic,
        "real_checkpoint_rgba_export": rgba_diagnostic,
        "gpu_inference_tested": False,
        "alpha_end_to_end_tested": True,
        "tile_seam_quality_certified": False,
        "quality_compared_to_V2": False,
        "print_certified": False,
    }
    (output_dir / "result.json").write_text(
        json.dumps(details, indent=2), encoding="utf-8"
    )
    print(json.dumps(details))


if __name__ == "__main__":
    main()
