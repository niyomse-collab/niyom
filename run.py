import os

# Importing app_v2 is intentionally done before smoke-test handling: the
# packaged EXE must prove that PyTorch/BasicSR/RealESRGAN imports are complete.
from signprint_ai.app_v2 import main

if __name__ == "__main__":
    if os.environ.get("NIYOMSIL_IMPORT_SMOKE") == "1":
        raise SystemExit(0)
    main()
