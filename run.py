import os
import sys


if __name__ == "__main__":
    # The experimental installer offers this one-time setup task before the
    # editor launches. Keep it ahead of app_v2 imports so provisioning does
    # not start the UI or display a second consent prompt.
    if sys.argv[1:] in (
        ["--provision-v211-four-ai"],
        ["--provision-v211-four-ai", "--silent"],
    ):
        from signprint_ai.v211_setup_cli import main as provision_main
        raise SystemExit(provision_main(silent="--silent" in sys.argv[1:]))

    if len(sys.argv) >= 2 and sys.argv[1] == "--diagnose-v211-four-ai":
        from tools.v211_shop_gpu_diagnostic import main as diagnostic_main
        raise SystemExit(diagnostic_main(sys.argv[2:]))

    # Import app_v2 before smoke handling so the frozen EXE proves that the
    # normal V2/PyTorch/BasicSR/RealESRGAN import graph is complete.
    from signprint_ai.app_v2 import main

    if os.environ.get("NIYOMSIL_PACKAGE_SMOKE") == "1":
        from signprint_ai.package_smoke import run
        raise SystemExit(run(os.environ["NIYOMSIL_SMOKE_OUTPUT"]))
    if os.environ.get("NIYOMSIL_UI_SMOKE") == "1":
        from signprint_ai.ui_smoke import run
        run()
        raise SystemExit(0)
    if os.environ.get("NIYOMSIL_FACE_BACKEND_SMOKE") == "1":
        from signprint_ai.face_module import FaceProtectionModule
        FaceProtectionModule().smoke_test("cpu")
        raise SystemExit(0)
    if os.environ.get("NIYOMSIL_IMPORT_SMOKE") == "1":
        # Frozen-package contract: verify experimental V2.1.1 adapters are
        # actually importable, not merely listed in the PyInstaller spec.
        # This does not download weights or execute any native GPU engine.
        import importlib
        for module_name in (
            "signprint_ai.v211_auto_setup",
            "signprint_ai.v211_setup_cli",
            "signprint_ai.v211_four_engine_bridge",
            "signprint_ai.v211_background_fusion",
            "tools.v211_provision_four_engines",
            "tools.v211_four_engine_run",
            "tools.v211_four_engine_fusion",
            "tools.v211_four_engine_tiled_inference",
            "tools.v211_shop_gpu_diagnostic",
        ):
            importlib.import_module(module_name)
        import tempfile
        from pathlib import Path
        from PIL import Image as PILImage
        from signprint_ai.large_image import vips

        pyvips = vips()
        image = pyvips.Image.black(8, 8, bands=3)
        assert image.width == 8 and len(image.write_to_memory()) == 8 * 8 * 3

        # The tiled runner relies on libvips' PNG loader and random-access
        # Region.fetch, not only on in-memory image construction. Exercise the
        # exact frozen binary path used by >18 MP disk-backed tile reads.
        with tempfile.TemporaryDirectory(prefix="niyomsil_vips_region_smoke_") as temporary:
            sample = Path(temporary) / "region.png"
            PILImage.new("RGB", (13, 11), (17, 31, 47)).save(sample, format="PNG")
            disk_image = pyvips.Image.new_from_file(
                str(sample), access="random", fail_on="error", unlimited=True
            )
            region = pyvips.Region.new(disk_image)
            pixels = region.fetch(3, 4, 5, 6)
            assert len(pixels) == 5 * 6 * 3
            assert bytes(pixels[:3]) == bytes((17, 31, 47))
            assert bytes(pixels[-3:]) == bytes((17, 31, 47))
            del region, disk_image
        raise SystemExit(0)
    main()
