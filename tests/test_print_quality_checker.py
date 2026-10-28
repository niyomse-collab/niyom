"""Self-contained QA checker regression tests using synthetic artwork only."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "qa" / "check_raster.py"


def invoke(tmp_path, src, dst, *flags):
    report = tmp_path / "report.json"
    p = subprocess.run([sys.executable, str(CHECKER), str(src), str(dst),
                        "--report", str(report), *flags], capture_output=True, text=True)
    assert report.exists(), f"QA checker did not write report; exit={p.returncode}; stdout={p.stdout}; stderr={p.stderr}"
    return p, json.loads(report.read_text(encoding="utf-8"))


def test_rgba_png_to_tiff_passes_exact_alpha(tmp_path):
    a = np.zeros((32, 40, 4), dtype=np.uint8)
    a[5:25, 6:30, :3] = (200, 40, 60)
    a[5:25, 6:30, 3] = 128
    src, dst = tmp_path / "src.png", tmp_path / "dst.tif"
    Image.fromarray(a).save(src)
    Image.fromarray(a).save(dst, dpi=(300, 300))
    p, result = invoke(tmp_path, src, dst, "--expect-same-size")
    assert p.returncode == 0
    assert result["checks"]["alpha_exact_same_size"]["status"] == "PASS"
    assert result["details"]["output_dpi"] == [300.0, 300.0]
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_missing_alpha_is_failure(tmp_path):
    a = np.zeros((10, 10, 4), dtype=np.uint8)
    a[2:8, 2:8, 3] = 255
    src, dst = tmp_path / "src.png", tmp_path / "dst.png"
    Image.fromarray(a).save(src)
    Image.fromarray(a[..., :3]).save(dst)
    p, result = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert result["checks"]["alpha_channel"]["status"] == "FAIL"


def test_alpha_mismatch_is_failure(tmp_path):
    a = np.zeros((10, 10, 4), dtype=np.uint8)
    a[..., 3] = 90
    b = a.copy()
    b[3, 3, 3] = 0
    src, dst = tmp_path / "src.png", tmp_path / "dst.png"
    Image.fromarray(a).save(src)
    Image.fromarray(b).save(dst)
    p, result = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert result["checks"]["alpha_exact_same_size"]["status"] == "FAIL"


def test_resize_never_claims_exact_alpha_validation(tmp_path):
    a = np.zeros((10, 10, 4), dtype=np.uint8)
    src, dst = tmp_path / "src.png", tmp_path / "dst.png"
    Image.fromarray(a).save(src)
    Image.fromarray(np.zeros((20, 20, 4), dtype=np.uint8)).save(dst)
    p, result = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert result["checks"]["alpha_exact_same_size"]["status"] == "NOT_TESTED"
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_truncated_rgb_output_fails_instead_of_claiming_decoded(tmp_path):
    # PIL can read a PNG header without decoding the complete pixel stream.
    a = np.random.default_rng(42).integers(0, 256, (256, 256, 3), dtype=np.uint8)
    src, dst = tmp_path / "src.png", tmp_path / "damaged.png"
    Image.fromarray(a).save(src)
    data = src.read_bytes()
    dst.write_bytes(data[:len(data) // 2])
    p, result = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert result["automated_checks"] == "FAIL"
    assert "error" in result
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_missing_input_still_writes_failure_report(tmp_path):
    src, dst = tmp_path / "missing.png", tmp_path / "output.png"
    Image.new("RGB", (8, 8), "white").save(dst)
    p, result = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert result["automated_checks"] == "FAIL"
    assert "error" in result
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_large_output_decode_is_not_claimed_without_full_read(tmp_path, monkeypatch):
    # Exercise memory guard without allocating a huge raster.
    import importlib.util
    spec = importlib.util.spec_from_file_location("printqa", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MAX_FULL_DECODE_PIXELS", 1)
    src, dst = tmp_path / "src.png", tmp_path / "output.png"
    Image.new("RGB", (8, 8), "white").save(src)
    Image.new("RGB", (8, 8), "white").save(dst)
    checks, _ = module.inspect(src, dst)
    assert checks["output_decodes"]["status"] == "NOT_TESTED"


def test_large_source_alpha_does_not_allocate_full_source(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("printqa", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MAX_FULL_DECODE_PIXELS", 64)
    source = tmp_path / "large_source.png"
    output = tmp_path / "small_output.png"
    Image.new("RGBA", (100, 100), (5, 70, 120, 128)).save(source)
    Image.new("RGBA", (4, 4), (5, 70, 120, 128)).save(output)

    original_convert = Image.Image.convert
    def prevent_full_conversion(image, *args, **kwargs):
        if image.size == (100, 100):
            raise AssertionError("Large source must never be decoded as a full RGBA raster")
        return original_convert(image, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "convert", prevent_full_conversion)
    checks, _ = module.inspect(source, output)
    assert checks["alpha_channel"]["status"] == "PASS"
    assert checks["alpha_exact_same_size"]["status"] == "NOT_TESTED"
    assert checks["alpha_edge_visual"]["status"] == "NOT_TESTED"


def test_resized_rgba_that_became_fully_opaque_is_failure(tmp_path):
    # A channel alone is not proof of transparency preservation.
    src, dst = tmp_path / "source.png", tmp_path / "resized.png"
    source = np.zeros((12, 12, 4), dtype=np.uint8)
    source[..., :3] = (210, 50, 80)
    source[..., 3] = 255
    source[:4, :, 3] = 0
    Image.fromarray(source, "RGBA").save(src)
    Image.new("RGBA", (24, 24), (210, 50, 80, 255)).save(dst)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert report["checks"]["alpha_channel"]["status"] == "PASS"
    assert report["checks"]["alpha_exact_same_size"]["status"] == "NOT_TESTED"
    assert report["checks"]["alpha_nonopaque_preserved"]["status"] == "FAIL"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_resized_rgba_with_transparency_retained_passes_alpha_guard(tmp_path):
    src, dst = tmp_path / "source.png", tmp_path / "resized.png"
    Image.new("RGBA", (12, 12), (210, 50, 80, 128)).save(src)
    Image.new("RGBA", (24, 24), (210, 50, 80, 128)).save(dst)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert report["checks"]["alpha_nonopaque_preserved"]["status"] == "PASS"
    assert report["checks"]["alpha_exact_same_size"]["status"] == "NOT_TESTED"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_truncated_source_fails_even_with_valid_output(tmp_path):
    # A source PNG header can be readable even if its pixel stream is cut off.
    rng = np.random.default_rng(2026)
    pixels = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
    src, dst = tmp_path / "damaged_source.png", tmp_path / "valid_output.png"
    Image.fromarray(pixels).save(dst)
    data = dst.read_bytes()
    src.write_bytes(data[:len(data) // 2])
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert report["automated_checks"] == "FAIL"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_source_full_decode_guard_does_not_allocate_large_input(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("printqa", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MAX_FULL_DECODE_PIXELS", 64)
    src, dst = tmp_path / "large.png", tmp_path / "small.png"
    Image.new("RGB", (100, 100), (20, 40, 60)).save(src)
    Image.new("RGB", (4, 4), (20, 40, 60)).save(dst)
    checks, _ = module.inspect(src, dst)
    assert checks["source_decodes"]["status"] == "NOT_TESTED"
    assert checks["output_decodes"]["status"] == "PASS"


def test_partial_alpha_lost_even_if_some_transparency_remains_fails(tmp_path):
    # Retaining fully transparent pixels is not enough for antialiased text.
    src, dst = tmp_path / "antialiased.png", tmp_path / "binary.png"
    original = np.zeros((24, 24, 4), dtype=np.uint8)
    original[..., :3] = (220, 60, 40)
    original[5:19, 5:19, 3] = 255
    original[5:19, 5, 3] = 128
    Image.fromarray(original, "RGBA").save(src)
    damaged = original.copy()
    damaged[..., 3] = np.where(damaged[..., 3] >= 128, 255, 0)
    Image.fromarray(damaged, "RGBA").save(dst)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert report["checks"]["alpha_channel"]["status"] == "PASS"
    assert report["checks"]["alpha_nonopaque_preserved"]["status"] == "PASS"
    assert report["checks"]["alpha_partial_preserved"]["status"] == "FAIL"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_partial_alpha_retained_does_not_claim_visual_fringe_pass(tmp_path):
    src, dst = tmp_path / "antialiased.png", tmp_path / "unchanged.png"
    Image.new("RGBA", (24, 24), (20, 90, 150, 128)).save(src)
    Image.new("RGBA", (24, 24), (20, 90, 150, 128)).save(dst)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert report["checks"]["source_decodes"]["status"] == "PASS"
    assert report["checks"]["alpha_partial_preserved"]["status"] == "PASS"
    assert report["checks"]["alpha_edge_visual"]["status"] == "NOT_TESTED"



def test_cmyk_export_from_transparent_png_is_opaque_by_design_not_alpha_failure(tmp_path):
    src, dst = tmp_path / "source.png", tmp_path / "print.tif"
    Image.new("RGBA", (24, 18), (210, 40, 80, 128)).save(src)
    Image.new("CMYK", (48, 36), (0, 100, 100, 0)).save(dst, dpi=(200, 200))
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert report["automated_checks"] == "PASS_WITH_UNTESTED"
    assert report["checks"]["alpha_channel"]["status"] == "NOT_APPLICABLE"
    assert report["checks"]["alpha_edge_visual"]["status"] == "NOT_TESTED"
    assert report["checks"]["cmyk_icc_consistency"]["status"] == "NOT_TESTED"
    assert report["checks"]["printer_ink_media_rip_match"]["status"] == "NOT_TESTED"
    assert report["details"]["source_alpha_export_policy"] == "flattened_for_opaque_format"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_cmyk_raster_with_embedded_rgb_icc_is_rejected(tmp_path):
    from PIL import ImageCms
    src, dst = tmp_path / "source.png", tmp_path / "wrong.tif"
    Image.new("RGB", (24, 18), (210, 40, 80)).save(src)
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("CMYK", (24, 18), (0, 0, 0, 0)).save(dst, icc_profile=srgb)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 1
    assert report["checks"]["cmyk_icc_consistency"]["status"] == "FAIL"
    assert report["details"]["output_icc"]["color_space"] == "RGB"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_rgba_to_jpeg_is_explicitly_opaque_export(tmp_path):
    src, dst = tmp_path / "source.png", tmp_path / "output.jpg"
    Image.new("RGBA", (24, 18), (100, 140, 50, 100)).save(src)
    Image.new("RGB", (24, 18), (100, 140, 50)).save(dst)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert report["checks"]["alpha_channel"]["status"] == "NOT_APPLICABLE"
    assert report["checks"]["alpha_edge_visual"]["status"] == "NOT_TESTED"
    assert report["print_certification"] == "NOT_CERTIFIED"


def test_rgb_embedded_srgb_metadata_is_not_printer_certification(tmp_path):
    from PIL import ImageCms
    src, dst = tmp_path / "source.png", tmp_path / "output.png"
    Image.new("RGB", (24, 18), (100, 140, 50)).save(src)
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (24, 18), (100, 140, 50)).save(dst, icc_profile=srgb)
    p, report = invoke(tmp_path, src, dst)
    assert p.returncode == 0
    assert report["details"]["output_icc"]["color_space"] == "RGB"
    assert report["checks"]["printer_ink_media_rip_match"]["status"] == "NOT_TESTED"
    assert report["print_certification"] == "NOT_CERTIFIED"
