"""Small synthetic fixtures only; customer images never enter the repository."""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image

PATH = Path(__file__).resolve().parents[1] / "qa" / "probe_cmyk_matte.py"
spec = importlib.util.spec_from_file_location("probe_cmyk_matte", PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def transparent_source(tmp_path):
    path = tmp_path / "transparent.png"
    data = np.zeros((78, 126, 4), dtype=np.uint8)
    data[:,:,:3] = [0, 0, 0]
    data[28:50, 44:82, :3] = [210, 30, 40]
    data[28:50, 44:82, 3] = 255
    Image.fromarray(data, "RGBA").save(path)
    return path


def test_rejects_cmky_near_black_in_transparent_source_regions(tmp_path):
    src = transparent_source(tmp_path)
    dst = tmp_path / "bad.tif"
    Image.new("CMYK", (252, 156), (224, 202, 186, 250)).save(dst)
    result = probe.inspect(src, dst)
    assert result["automated_check"] == "FAIL"
    assert result["bad_sample_count"] >= 3
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_accepts_white_matte_but_never_certifies_print(tmp_path):
    src = transparent_source(tmp_path)
    dst = tmp_path / "white.tif"
    Image.new("CMYK", (252, 156), (0, 0, 0, 0)).save(dst)
    result = probe.inspect(src, dst)
    assert result["automated_check"] == "PASS"
    assert result["sample_count"] >= 3
    assert result["bad_sample_count"] == 0
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_rgb_output_is_a_failure_not_a_false_pass(tmp_path):
    src = transparent_source(tmp_path)
    dst = tmp_path / "wrong.png"
    Image.new("RGB", (252, 156), "white").save(dst)
    assert probe.inspect(src, dst)["automated_check"] == "FAIL"


def test_large_tiff_without_pyvips_abstains_instead_of_allocating(tmp_path, monkeypatch):
    import sys
    src = transparent_source(tmp_path)
    dst = tmp_path / "large.tif"
    Image.new("CMYK", (252, 156), (0, 0, 0, 0)).save(dst)
    monkeypatch.setattr(probe, "MAX_FULL_OUTPUT_PIXELS", 1)
    monkeypatch.setitem(sys.modules, "pyvips", None)
    result = probe.inspect(src, dst)
    assert result["automated_check"] == "NOT_TESTED"
    assert result["sample_count"] if "sample_count" in result else True


def test_alpha_source_is_required_for_matte_claim(tmp_path):
    src = tmp_path / "rgb.png"
    dst = tmp_path / "white.tif"
    Image.new("RGB", (126, 78), "black").save(src)
    Image.new("CMYK", (252, 156), (0, 0, 0, 0)).save(dst)
    assert probe.inspect(src, dst)["automated_check"] == "NOT_TESTED"


def test_cli_writes_not_certified_json_report(tmp_path):
    src = transparent_source(tmp_path)
    dst = tmp_path / "out.tif"
    Image.new("CMYK", (252, 156), (0, 0, 0, 0)).save(dst)
    report = tmp_path / "report.json"
    assert probe.main([str(src), str(dst), "--report", str(report)]) == 0
    import json
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["automated_check"] == "PASS"
    assert data["print_certification"] == "NOT_CERTIFIED"
