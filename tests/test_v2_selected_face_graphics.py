"""Face-protected mixed posters still receive v2 lettering cleanup."""
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image

from signprint_ai import niyomsil_core_adapter as core
from signprint_ai.processing import EnhanceSettings


def test_selected_face_does_not_disable_nonface_graphic_refinement(
    tmp_path, monkeypatch
):
    source = tmp_path / "poster.png"
    original = np.full((72, 80, 3), (244, 226, 182), dtype=np.uint8)
    original[17:61, 9:71] = (24, 45, 125)
    original = cv2.GaussianBlur(original, (0, 0), 0.9)
    Image.fromarray(original, "RGB").save(source)

    class FakeEngine:
        def enhance(self, input_path, output_path, scale, **kwargs):
            with Image.open(input_path) as image:
                image.convert("RGB").resize(
                    (image.width * scale, image.height * scale),
                    Image.Resampling.BICUBIC,
                ).save(output_path)

        def device_name(self):
            return "CPU"

    class FakeManager:
        def __init__(self):
            self.engine = None
            self.device_manager = SimpleNamespace(
                get_default_device=lambda: SimpleNamespace(
                    device_id="cpu", name="CPU"
                )
            )

        def create_engine(self, device):
            self.engine = FakeEngine()
            return self.engine

    class FakeFace:
        def apply(self, image, **kwargs):
            return image, SimpleNamespace(as_dict=lambda: {
                "enabled": True, "applied": True, "face_count": 1,
                "mode": "protect", "strength": 35, "skipped_reason": None,
            })

    adapter = core.NiyomSilpCoreAdapter.__new__(core.NiyomSilpCoreAdapter)
    adapter.engine_manager = FakeManager()
    adapter.face_module = FakeFace()
    settings = EnhanceSettings(
        ai_scale=4, face_protection=True,
        face_regions=((0.45, 0.12, 0.80, 0.80),),
    )
    untouched = tmp_path / "unrefined.png"
    output = tmp_path / "refined.png"

    real_refine = core.refine_sign_edges
    monkeypatch.setattr(
        core, "refine_sign_edges",
        lambda image, **kwargs: image,
    )
    adapter.process(source, untouched, settings)
    with Image.open(untouched) as image:
        baseline = np.asarray(image).copy()

    seen = []

    def spy(image, protected_regions=None):
        seen.append(protected_regions)
        return real_refine(image, protected_regions=protected_regions)

    monkeypatch.setattr(core, "refine_sign_edges", spy)
    adapter.process(source, output, settings)
    with Image.open(output) as image:
        processed = np.asarray(image).copy()

    assert seen and seen[0] is not None
    # Face pixels remain identical to the simulated restored face output.
    x1, y1, x2, y2 = seen[0][0]
    left, right = int(x1 * processed.shape[1]), int(x2 * processed.shape[1])
    top, bottom = int(y1 * processed.shape[0]), int(y2 * processed.shape[0])
    np.testing.assert_array_equal(
        processed[top:bottom, left:right], baseline[top:bottom, left:right]
    )
    assert np.any(processed[72:208, 34:63] != baseline[72:208, 34:63])
