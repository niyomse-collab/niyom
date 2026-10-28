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
