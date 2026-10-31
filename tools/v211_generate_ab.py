"""Run the actual V2 processor and V2+HAT Assist on one private image.

Example (inside a verified V2.1.1 runtime with BOTH model weights):
  python -m tools.v211_generate_ab --input image.png --out ./private-qa --scale 2

This local research tool does not publish or upload photos. It uses identical
image dimensions, output settings and optional confirmed face ROIs in both
passes. The generated report is evidence for human judgement, NOT a quality
certificate. Limit diagnostic output to a representative <=16MP crop; this
does not impose any size limit on the production enhancer.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from signprint_ai.large_image import image_size
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.v21_graphics_ai import V21Settings
from tools.v211_ab_report import _check_qa_size, compare_images, render_comparison


def _validate_faces(faces):
    if faces is None:
        return ()
    if not isinstance(faces, list):
        raise ValueError("Faces JSON must contain a list of normalized rectangles")
    import math
    result = []
    for face in faces:
        if not isinstance(face, (tuple, list)) or len(face) != 4:
            raise ValueError("Each face ROI must have four coordinates")
        a, b, c, d = (float(v) for v in face)
        if not all(math.isfinite(v) for v in (a, b, c, d)):
            raise ValueError("Face ROI contains a NaN or infinite coordinate")
        if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
            raise ValueError("Face ROI is outside normalized coordinates")
        result.append((a, b, c, d))
    return tuple(result)


def run_pair(source, destination, *, scale=2, dpi=300, device="AUTO",
             faces=(), face_mode="recover", face_strength=65,
             adapter=None, assist_model="v2_hat_assist"):
    """Produce matching V2 and assisted PNGs plus noncertifying A/B evidence."""
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    if scale not in (2, 4):
        raise ValueError("A/B model-scale must be 2x or 4x")
    if not 1 <= dpi <= 1200:
        raise ValueError("Invalid DPI")
    if not 10 <= face_strength <= 80:
        raise ValueError("Invalid face strength")
    if face_mode not in ("recover", "studio ai"):
        raise ValueError("A/B face mode must be recover or studio ai")
    # Fail before inference if comparison output would exceed the bounded
    # in-memory QA tool, rather than running expensive AI and then failing.
    width, height = image_size(source)
    _check_qa_size((width * scale, height * scale))
    selected_faces = _validate_faces([list(f) for f in faces])
    engine = adapter if adapter is not None else NiyomSilpCoreAdapter()
    if assist_model not in ("v2_hat_assist", "v2_swinir_pre", "v2_nafnet_deblur", "v2_nafnet_photo_only"):
        raise ValueError("Unknown A/B assistant model")
    if not engine.selected_model_available(assist_model):
        raise RuntimeError("V2 + selected AI comparison requires both verified model weights")
    destination.mkdir(parents=True, exist_ok=True)
    settings = V21Settings(
        ai_scale=scale,
        device=device,
        dpi=dpi,
        face_protection=bool(selected_faces),
        face_regions=(selected_faces if selected_faces else None),
        face_mode=face_mode,
        face_strength=face_strength,
        v1_baseline=True,
        v21_v2_quality_baseline=True,
        v21_precision_ink=False,
        graphic_ai=False,
        export_format="PNG",
        color_mode="RGB",
    )
    reference = destination / "V2_reference.png"
    assisted_name = {
        "v2_hat_assist": "V211_V2_plus_HAT.png",
        "v2_swinir_pre": "V211_V2_plus_SwinIR.png",
        "v2_nafnet_deblur": "V211_V2_plus_NAFNet.png",
        "v2_nafnet_photo_only": "V211_V2_plus_NAFNet_PhotoOnly.png",
    }[assist_model]
    assisted = destination / assisted_name
    first = engine.process(
        source, reference, replace(settings, v211_photo_model="real_esrgan"),
        use_ai=True,
    )
    second = engine.process(
        source, assisted, replace(settings, v211_photo_model=assist_model),
        use_ai=True,
    )
    report = compare_images(reference, assisted, face_regions=selected_faces)
    report["processing"] = {
        "v2_model": first.get("model"),
        "assisted_model": second.get("model"),
        "scale": scale,
        "dpi": dpi,
        "device": device,
        "face_mode": face_mode if selected_faces else None,
        "selected_face_count": len(selected_faces),
    }
    report["no_customer_files_uploaded"] = True
    (destination / "A_B_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    render_comparison(reference, assisted, destination / "V2_VS_SUPER_AI.png")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scale", choices=(2, 4), type=int, default=2)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--device", default="AUTO")
    parser.add_argument("--assist", choices=("v2_hat_assist", "v2_swinir_pre", "v2_nafnet_deblur", "v2_nafnet_photo_only"), default="v2_hat_assist")
    parser.add_argument("--faces", type=Path, help="Optional private JSON face ROI list")
    parser.add_argument("--face-mode", choices=("recover", "studio ai"), default="recover")
    parser.add_argument("--face-strength", type=int, default=65)
    args = parser.parse_args(argv)
    faces = _validate_faces(
        json.loads(args.faces.read_text(encoding="utf-8")) if args.faces else []
    )
    report = run_pair(args.input, args.out, scale=args.scale, dpi=args.dpi,
                      device=args.device, faces=faces,
                      face_mode=args.face_mode, face_strength=args.face_strength,
                      assist_model=args.assist)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
