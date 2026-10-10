"""Separate NiyomSilp Independent Core TEST executable entrypoint."""
import os


def test_import() -> int:
    from independent_core.desktop_adapter import DesktopTestAdapter
    from independent_core.print_output import PrintSpec
    from independent_core.icc_library import list_external_profiles  # noqa: F401
    adapter = DesktopTestAdapter()
    if not adapter.available:
        raise FileNotFoundError(f"Model missing in TEST package: {adapter.model_path}")
    assert PrintSpec(width=100, height=50, dpi=150).target_pixels() == (5906, 2953)
    return 0


def test_real_inference() -> int:
    """Small actual RealESRGAN x4plus inference test, in a temporary directory."""
    import tempfile
    from pathlib import Path
    import numpy as np
    from PIL import Image
    from independent_core.desktop_adapter import DesktopTestAdapter
    from signprint_ai.processing import EnhanceSettings

    with tempfile.TemporaryDirectory(prefix="NiyomSilpCoreTest_") as folder:
        src = Path(folder) / "test_input.png"
        output = Path(folder) / "test_result.png"
        px = np.empty((6, 9, 3), dtype=np.uint8)
        px[:, :, :] = (15, 23, 48)
        px[:3, :4] = (244, 19, 65)
        Image.fromarray(px).save(src)
        config = EnhanceSettings(ai_scale=2, dpi=150, color_mode="RGB",
                                 face_protection=False)
        result = DesktopTestAdapter().process(src, output, config, use_ai=True)
        assert result["output_size"] == (18, 12), result
        with Image.open(output) as im:
            assert im.mode == "RGB" and im.size == (18, 12), im.size
    return 0


if __name__ == "__main__":
    if os.environ.get("NIYOMSIL_INDEPENDENT_SMOKE") == "1":
        raise SystemExit(test_import())
    if os.environ.get("NIYOMSIL_INDEPENDENT_INFER_SMOKE") == "1":
        raise SystemExit(test_real_inference())
    from independent_core.gui_test import main
    main()
