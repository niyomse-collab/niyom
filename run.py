import os
import sys



def _run_v211_tiff_smoke(output_dir):
    """Exercise the frozen V2.1.1 TIFF/BigTIFF -> libvips -> QA path offline."""
    import hashlib
    import json
    import shutil
    import tempfile
    from pathlib import Path

    import numpy as np
    import tifffile
    from PIL import Image, ImageCms

    from signprint_ai.v211_large_image_bridge import (
        inspect_image,
        prepare_native_2x_inputs_streamed,
        save_cropped_png_streamed,
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    def digest(path):
        with Path(path).open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    with tempfile.TemporaryDirectory(
        prefix="niyomsil-v211-frozen-tiff-", dir=output
    ) as temporary:
        root = Path(temporary)
        source = root / "source-bigtiff.tif"
        baseline = root / "accepted-v2-bigtiff.tif"
        work = root / "work"
        qa = work / "qa.png"

        def write_bigtiff(path, size, colour):
            width, height = size
            pixels = np.empty((height, width, 3), dtype=np.uint8)
            pixels[:] = colour
            tifffile.imwrite(
                path,
                pixels,
                bigtiff=True,
                photometric="rgb",
                resolution=(300, 300),
                resolutionunit="INCH",
                extratags=[(34675, "B", len(profile), profile, False)],
            )

        # Odd target dimensions exercise even padding and exact QA cropping.
        write_bigtiff(source, (128, 96), (220, 30, 40))
        write_bigtiff(baseline, (257, 193), (245, 245, 245))
        baseline_sha_before = digest(baseline)

        source_size, source_mode, source_metadata = inspect_image(
            source, orient=True
        )
        target_size, target_mode, metadata = inspect_image(baseline)
        if source_size != (128, 96) or source_mode != "RGB":
            raise RuntimeError("Frozen TIFF source header inspection failed")
        if target_size != (257, 193) or target_mode != "RGB":
            raise RuntimeError("Frozen accepted-V2 TIFF header inspection failed")
        if source_metadata.get("icc_profile") != profile:
            raise RuntimeError("Frozen source TIFF ICC profile was not preserved")
        if metadata.get("icc_profile") != profile:
            raise RuntimeError("Frozen V2 TIFF ICC profile was not preserved")

        seed, reference, actual_target, padded, actual_source, returned_metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work, resize_mode="fit"
            )
        )
        if actual_target != (257, 193) or padded != (258, 194):
            raise RuntimeError("Frozen BigTIFF even-padding geometry is incorrect")
        if actual_source != (128, 96):
            raise RuntimeError("Frozen BigTIFF source geometry changed")
        with Image.open(seed) as seed_image:
            if seed_image.size != (129, 97):
                raise RuntimeError("Frozen BigTIFF half-target seed geometry is incorrect")
            if seed_image.info.get("icc_profile") != profile:
                raise RuntimeError("Frozen seed ICC profile was not preserved")
            if abs(float(seed_image.info["dpi"][0]) - 300) > 0.1:
                raise RuntimeError("Frozen seed DPI was not preserved")
        with Image.open(reference) as reference_image:
            if reference_image.size != padded:
                raise RuntimeError("Frozen V2 reference padding is incorrect")
            if reference_image.info.get("icc_profile") != profile:
                raise RuntimeError("Frozen V2 reference ICC profile was not preserved")

        candidate = work / "candidate.png"
        shutil.copyfile(reference, candidate)
        save_cropped_png_streamed(
            candidate,
            qa,
            target_size=actual_target,
            padded_size=padded,
            mode="RGB",
            metadata=returned_metadata,
        )
        with Image.open(qa) as qa_image:
            if qa_image.size != actual_target or qa_image.mode != "RGB":
                raise RuntimeError("Frozen streamed QA crop geometry/mode is incorrect")
            if qa_image.info.get("icc_profile") != profile:
                raise RuntimeError("Frozen QA crop ICC profile was not preserved")
            dpi = qa_image.info.get("dpi")
            if not dpi or abs(float(dpi[0]) - 300) > 0.1:
                raise RuntimeError("Frozen QA crop DPI was not preserved")

        multipage = root / "must-reject-multipage-bigtiff.tif"
        with tifffile.TiffWriter(multipage, bigtiff=True) as writer:
            writer.write(np.zeros((16, 16, 3), dtype=np.uint8), photometric="rgb")
            writer.write(np.ones((16, 16, 3), dtype=np.uint8), photometric="rgb")
        try:
            inspect_image(multipage)
        except ValueError:
            multipage_rejected = True
        else:
            raise RuntimeError("Frozen BigTIFF reader accepted a multi-page TIFF")

        baseline_sha_after = digest(baseline)
        if baseline_sha_after != baseline_sha_before:
            raise RuntimeError("Frozen TIFF smoke modified the accepted V2 raster")

    report = {
        "passed": True,
        "single_page_bigtiff_inspection": True,
        "disk_backed_seed_and_qa": True,
        "multipage_tiff_rejected": multipage_rejected,
        "icc_preserved": True,
        "dpi_preserved": True,
        "odd_target_crop_exact": True,
        "accepted_v2_sha256_unchanged": True,
        "target_size": [257, 193],
        "seed_size": [129, 97],
        "padded_size": [258, 194],
        "gpu_runtime_initialized": False,
        "native_ai_engines_started": False,
        "network_access": False,
        "customer_files_accessed": False,
    }
    (output / "v211-frozen-tiff-smoke.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0


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

    if os.environ.get("NIYOMSIL_V211_TIFF_SMOKE") == "1":
        output_dir = os.environ.get("NIYOMSIL_SMOKE_OUTPUT")
        if not output_dir:
            raise SystemExit("NIYOMSIL_SMOKE_OUTPUT is required for the TIFF smoke")
        raise SystemExit(_run_v211_tiff_smoke(output_dir))

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
