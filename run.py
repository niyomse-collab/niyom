import os

# Importing app_v2 is intentionally done before smoke-test handling: the
# packaged EXE must prove that PyTorch/BasicSR/RealESRGAN imports are complete.
from signprint_ai.app_v2 import main

if __name__ == "__main__":
    if os.environ.get("NIYOMSIL_UI_SMOKE") == "1":
        from signprint_ai.ui_smoke import run
        run()
        raise SystemExit(0)
    if os.environ.get("NIYOMSIL_FACE_BACKEND_SMOKE") == "1":
        from signprint_ai.face_module import FaceProtectionModule
        FaceProtectionModule().smoke_test("cpu")
        raise SystemExit(0)
    if os.environ.get("NIYOMSIL_IMPORT_SMOKE") == "1":
        raise SystemExit(0)
    main()
