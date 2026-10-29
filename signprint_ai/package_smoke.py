"""Run real packaged inference and large-image I/O without a GUI or GPU."""
from pathlib import Path
import hashlib
import json
import struct
import tempfile
import time
import traceback

import numpy as np
from PIL import Image


def run(output_dir):
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        report = _run(folder)
        (folder / "package-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        # This is a windowed PyInstaller EXE (console=False). Re-raising here
        # may display a modal error dialog and keep the runner alive until the
        # 20-minute watchdog fires. Persist the traceback and exit nonzero.
        (folder / "package-smoke-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    return 0


def _run(folder):
    import torch
    from . import large_image
    from .independent_core import DeviceInfo, RealESRGANEngine, model_path
    from .niyomsil_core_adapter import NiyomSilpCoreAdapter
    from .processing import EnhanceSettings, print_pixels
    from .release_info import load_release_info

    torch.set_num_threads(2)
    info = load_release_info()
    assert info["channel"] == "v2", "Wrong installer release channel"
    checkpoint = model_path()
    with checkpoint.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert digest == "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
    adapter = NiyomSilpCoreAdapter()
    report = {"release": info, "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
              "model_sha256": digest, "checks": []}
    with tempfile.TemporaryDirectory(prefix="niyomsil_packaged_", dir=folder) as temporary:
        work = Path(temporary)
        source = work / "source.png"
        pixels = np.arange(17*13*3, dtype="uint16").reshape(13,17,3).astype("uint8")
        Image.fromarray(pixels).save(source)
        engine = RealESRGANEngine(DeviceInfo("cpu", "CPU", "CPU"))
        engine.upsampler.tile_size = 8  # Exercise several real tiles on a small CI sample.
        reference = work / "reference4.png"
        engine.enhance(source, reference, 4)

        def choose(device):
            assert device == "cpu"
            adapter.engine_manager.engine = engine
            return engine

        adapter.engine_manager.create_engine = choose
        limit = large_image.IN_MEMORY_PIXELS
        large_image.IN_MEMORY_PIXELS = 1
        try:
            for scale in (2, 4, 8, 16):
                destination = work / f"ai_{scale}.png"
                started = time.monotonic()
                result = adapter.process(source, destination, EnhanceSettings(ai_scale=scale, device="cpu", denoise=0, flat_smoothing=0, text_graphic_boost=0, sharpness=0, contrast=0, saturation=0))
                with Image.open(destination) as image:
                    assert image.size == (17*scale, 13*scale)
                    assert np.asarray(image).std() > 0
                    if scale == 4:
                        with Image.open(reference) as baseline:
                            np.testing.assert_array_equal(np.asarray(image), np.asarray(baseline))
                assert engine.upsampler.img is None and engine.upsampler.output is None
                report["checks"].append({"name": f"real_ai_{scale}x", "size": result["output_size"],
                                          "seconds": round(time.monotonic()-started, 3)})
        finally:
            large_image.IN_MEMORY_PIXELS = limit

        if info.get("version", "").startswith("2.1."):
            from .v21_graphics_ai import V21Settings
            graphic_source = work / "graphic_source.png"
            graphic_pixels = np.full((32, 40, 3), 245, np.uint8)
            graphic_pixels[8:24, 8:32] = (180, 20, 110)
            Image.fromarray(graphic_pixels).save(graphic_source)
            # A 40x32 source requesting 208x166 print pixels needs >4x.
            # Accepted V2 used two real AI passes (4x then 2x), not one 4x
            # inference and a non-neural 5.2x resize. Both paths must work
            # inside the installed EXE, not only in source-level regression.
            graphic_output = work / "v2_quality_baseline_print.png"
            graphic_settings = V21Settings(
                ai_scale=4, device="cpu", text_graphic_boost=28,
                graphic_ai=True, v21_v2_quality_baseline=True,
                v21_precision_ink=True, flat_smoothing=80,
                print_width=2.08, print_height=1.66,
                print_unit="inch", dpi=100,
            )
            result = adapter.process(graphic_source, graphic_output, graphic_settings)
            assert result["ai_scale"] == 8 and result["output_size"] == (208, 166)
            assert result.get("graphic_ai_model") is None
            with Image.open(graphic_output) as image:
                assert image.size == (208, 166) and np.asarray(image).std() > 0
            report["checks"].append({
                "name": "installed_exe_v21_v2_quality_two_real_ai_passes",
                "inference": "4x_then_2x", "ai_scale": 8,
                "precision_ink": True, "size": [208, 166],
            })

            # Experimental V2.1 graphics model must load separately and must
            # *not* change the approved V2-mode neural pass strategy.
            experimental_output = work / "graphic_v21_anime_4x.png"
            experiment_settings = V21Settings(
                ai_scale=4, device="cpu", text_graphic_boost=28,
                graphic_ai=True, v21_v2_quality_baseline=False,
                print_width=2.08, print_height=1.66,
                print_unit="inch", dpi=100,
            )
            experiment = adapter.process(
                graphic_source, experimental_output, experiment_settings
            )
            assert experiment["ai_scale"] == 4
            assert experiment["output_size"] == (208, 166)
            assert experiment.get("graphic_ai_model") == "RealESRGAN_x4plus_anime_6B"
            with Image.open(experimental_output) as image:
                assert image.size == (208, 166) and np.asarray(image).std() > 0
            report["checks"].append({
                "name": "installed_exe_v21_experimental_anime_model",
                "ai_scale": 4, "size": [208, 166],
            })

        # Verify transparent print artwork through the *packaged EXE*
        # (not only source-level mocked ICC tests). The zero-alpha RGB
        # deliberately contains hidden black: a black JPEG background is
        # always a failure, even if the rest of the image looks sharp.
        transparent_source = work / "transparent_test.png"
        rgba = np.zeros((48, 64, 4), dtype=np.uint8)
        rgba[14:34, 20:44, :3] = (25, 105, 215)
        rgba[14:34, 20:44, 3] = 255
        rgba[10, 10, :3] = (210, 30, 40)
        rgba[10, 10, 3] = 128
        Image.fromarray(rgba, "RGBA").save(transparent_source)
        old_limit = large_image.IN_MEMORY_PIXELS
        try:
            large_image.IN_MEMORY_PIXELS = 1
            no_effects = EnhanceSettings(
                ai_scale=1, device="cpu", denoise=0, flat_smoothing=0,
                text_graphic_boost=0, sharpness=0, contrast=0, saturation=0,
                resize_mode="stretch",
            )
            transparent_png = work / "transparent_roundtrip.png"
            png_result = adapter.process(transparent_source, transparent_png, no_effects, use_ai=False)
            with Image.open(transparent_png) as result_image:
                assert result_image.mode == "RGBA"
                assert result_image.size == (64, 48)
                assert result_image.getpixel((0, 0))[3] == 0
                assert result_image.getpixel((10, 10))[3] == 128
                assert result_image.getpixel((32, 24))[3] == 255

            white_jpeg = work / "transparent_to_white.jpg"
            jpeg_result = adapter.process(transparent_source, white_jpeg, no_effects, use_ai=False)
            with Image.open(white_jpeg) as result_image:
                assert result_image.mode == "RGB"
                assert min(result_image.getpixel((0, 0))) >= 245
                assert min(result_image.getpixel((63, 47))) >= 245
                middle = result_image.getpixel((32, 24))
                assert middle[2] > middle[1] > middle[0], middle
            report["checks"].append({
                "name": "installed_exe_disk_rgba_png_alpha_and_jpeg_white_matte",
                "mode": [png_result["processing_mode"], jpeg_result["processing_mode"]],
                "size": [64, 48],
                "transparent_corner": "jpeg_white",
                "partial_alpha": "png_128",
            })

            # Validate the exact libvips RGB -> white matte stage that feeds
            # CMYK icc_transform. Do not require a private printer profile in
            # public CI; actual ICC conversion remains a separate print gate.
            cmyk_input = large_image.prepare_source_alpha_for_export(
                large_image.as_rgb(large_image.open_vips(transparent_source)),
                transparent_source, (64, 48),
                EnhanceSettings(ai_scale=1, device="cpu",
                                resize_mode="stretch", color_mode="CMYK"),
                work / "synthetic_cmyk_target.tif",
            )
            assert cmyk_input.bands == 3 and not cmyk_input.hasalpha()
            cm = large_image.to_pillow(cmyk_input)
            assert cm.getpixel((0, 0)) == (255, 255, 255)
            assert cm.getpixel((63, 47)) == (255, 255, 255)
            assert cm.getpixel((32, 24)) == (25, 105, 215)
            expect_half = tuple(round((v * 128 + 255 * 127) / 255)
                                for v in (210, 30, 40))
            assert all(abs(a - b) <= 2 for a, b
                       in zip(cm.getpixel((10, 10)), expect_half))
            report["checks"].append({
                "name": "installed_exe_libvips_pre_cmyk_icc_white_matte",
                "transparent_corner": "rgb_white",
                "half_alpha": list(cm.getpixel((10, 10))),
                "note": "Pre-ICC stage only; actual CMYK printer profile untested",
            })
        finally:
            large_image.IN_MEMORY_PIXELS = old_limit

        Image.new("RGB", (60,40), (41,123,207)).save(source)
        destination = work / "large_banner.png"
        settings = EnhanceSettings(print_width=700, print_height=100, print_unit="cm",
                                   dpi=300, resize_mode="stretch", device="cpu")
        result = adapter.process(source, destination, settings, use_ai=False)
        with destination.open("rb") as stream:
            header = stream.read(33)
        expected = print_pixels(700,100,"cm",300)
        assert struct.unpack(">II",header[16:24]) == expected == result["output_size"]
        report["checks"].append({"name": "large_banner_300dpi", "size": expected})

        source = work / "large_source.png"
        image = large_image.vips().Image.black(20000,10000,bands=3).new_from_image([41,123,207])
        image.pngsave(str(source),compression=3)
        image = None
        assert large_image.thumbnail(source,(1200,800)).size == (1200,600)
        result = adapter.process(source,work/"large_copy.png",EnhanceSettings(ai_scale=1),use_ai=False)
        assert result["output_size"] == (20000,10000)
        report["checks"].append({"name": "large_source_200M", "size": result["output_size"]})

        stopped = [False]
        existing = work / "existing.png"
        existing.write_bytes(b"previous output")
        def progress(value, label):
            if value >= 99:
                stopped[0] = True
        try:
            adapter.process(source,existing,EnhanceSettings(ai_scale=1),use_ai=False,
                            progress=progress,cancel=lambda: stopped[0])
        except InterruptedError:
            pass
        else:
            raise AssertionError("Cancellation did not stop the job")
        assert existing.read_bytes() == b"previous output"
        assert not list(work.glob(".niyomsil*"))
        report["checks"].append({"name": "cancel_preserves_output_and_closes_files"})
    report["passed"] = True
    return report
