"""GitHub Actions real-inference experiment for a separate HAT checkpoint.

This only proves execution and dimensions with a synthetic RGB crop.
It does not certify image quality, customer artwork, model rights, or print.
"""
from __future__ import annotations

import json
from pathlib import Path
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
        "quality_compared_to_V2": False,
        "print_certified": False,
    }
    (output_dir / "result.json").write_text(
        json.dumps(details, indent=2), encoding="utf-8"
    )
    print(json.dumps(details))


if __name__ == "__main__":
    main()
