import os
import sys


if __name__ == "__main__":
    # The uninstaller reaches this command only after an explicit Yes choice.
    # The supplied path is validated against the dedicated per-profile cache
    # location; cleanup never follows symlinks/junctions or touches unknown files.
    if (len(sys.argv) == 5
            and sys.argv[1:4] == [
                "--remove-v211-four-ai-assets",
                "--confirmed-by-user",
                "--data-root",
            ]):
        from signprint_ai.v211_setup_cli import cleanup_four_engine_assets
        try:
            cleanup_four_engine_assets(sys.argv[4], confirmed=True)
        except Exception:
            raise SystemExit(1)
        raise SystemExit(0)

    # The experimental installer offers this one-time setup task before the
    # editor launches. Keep it ahead of app_v2 imports so provisioning does
    # not start the UI or display a second consent prompt.
    if sys.argv[1:] in (
        ["--provision-v211-four-ai"],
        ["--provision-v211-four-ai", "--silent"],
        ["--provision-v211-four-ai", "--check-only"],
    ):
        from signprint_ai.v211_setup_cli import main as provision_main
        raise SystemExit(provision_main(
            silent="--silent" in sys.argv[1:],
            preflight_only="--check-only" in sys.argv[1:],
        ))

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
            "signprint_ai.v211_large_image_bridge",
            "tifffile",
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

        # Exercise the optional scientific-runtime imports that PyInstaller
        # warned about. This is CPU-only and runs only in the explicit package
        # smoke mode; it does not initialize CUDA, load a native AI model, or
        # download anything. Numba's optional TBB backend is deliberately not
        # required: the smoke verifies its bundled workqueue fallback instead.
        try:
            import json
            import math
            import numpy as np
            import scipy
            from scipy import special

            erf_value = float(special.erf(1.0))
            if not math.isfinite(erf_value) or erf_value <= 0:
                raise RuntimeError("SciPy special-function smoke returned an invalid value")

            os.environ["NUMBA_THREADING_LAYER"] = "workqueue"
            import numba

            @numba.njit(parallel=True)
            def _numba_workqueue_sum(values):
                total = 0
                for index in numba.prange(values.size):
                    total += values[index]
                return total

            probe_values = np.arange(32, dtype=np.int64)
            parallel_sum = int(_numba_workqueue_sum(probe_values))
            threading_layer = numba.threading_layer()
            if parallel_sum != 496 or threading_layer != "workqueue":
                raise RuntimeError("Numba workqueue fallback smoke failed")

            import cffi
            import pycparser

            ffi = cffi.FFI()
            ffi.cdef(
                "typedef unsigned long v211_smoke_size_t; "
                "int v211_smoke_add(int left, int right);"
            )

            dependency_report = {
                "scipy_version": scipy.__version__,
                "scipy_special_erf_finite": True,
                "scipy_special_erf_1": erf_value,
                "numba_version": numba.__version__,
                "numba_threading_layer": threading_layer,
                "numba_workqueue_parallel_sum": parallel_sum,
                "cffi_version": cffi.__version__,
                "pycparser_version": pycparser.__version__,
                "pycparser_cffi_cdef_parse": True,
                "gpu_runtime_initialized": False,
                "native_ai_engines_started": False,
                "network_access": False,
            }
            report_path = Path(os.environ["NIYOMSIL_SMOKE_OUTPUT"]) / (
                "optional-runtime-dependency-smoke.json"
            )
            report_path.write_text(
                json.dumps(dependency_report, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            error_path = Path(os.environ["NIYOMSIL_SMOKE_OUTPUT"]) / (
                "package-smoke-error.txt"
            )
            error_path.write_text(
                "Optional runtime dependency smoke failed: "
                + type(exc).__name__ + ": " + str(exc),
                encoding="utf-8",
            )
            raise
        raise SystemExit(0)
    main()
