import os

# Importing app_v2 is intentionally done before smoke-test handling: the
# packaged EXE must prove that PyTorch/BasicSR/RealESRGAN imports are complete.
from signprint_ai.app_v2 import main

if __name__ == "__main__":
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
        from signprint_ai.large_image import vips
        image = vips().Image.black(8, 8, bands=3)
        assert image.width == 8 and len(image.write_to_memory()) == 8 * 8 * 3
        raise SystemExit(0)
    main()
