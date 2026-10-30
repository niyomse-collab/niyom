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
from PIL import Image

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
            tiled_std = float(np.asarray(tiled_output).std())
        if tiled_result["tiles"] <= 1 or tiled_std <= 1:
            raise AssertionError("HAT did not perform meaningful multi-tile inference")

    output_dir = Path("hat-inference-proof")
    output_dir.mkdir(exist_ok=True)
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
        "gpu_inference_tested": False,
        "alpha_end_to_end_tested": False,
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
