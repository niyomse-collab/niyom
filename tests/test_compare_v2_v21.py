"""Synthetic-only quality screening; never check customer artwork into Git."""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "qa" / "compare_v2_v21.py"
spec = importlib.util.spec_from_file_location("compare_v21", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def fixture(tmp_path, noisy=10, weaken=False, alpha=False):
    a = np.full((160, 180, 3), (225, 60, 80), np.uint8)
    a[:, 90:] = (30, 45, 175)
    if weaken:
        for dx in range(-9, 10):
            f = (dx+9)/18
            a[:, 90+dx] = np.rint(
                np.array([225, 60, 80])*(1-f)
                + np.array([30, 45, 175])*f
            ).astype("uint8")
    noise = np.random.default_rng(44).integers(
        -noisy, noisy+1, (90, 60, 3)
    )
    a[15:105, 10:70] = np.clip(
        a[15:105, 10:70].astype("int")+noise, 0, 255
    ).astype("uint8")
    if alpha:
        a = np.dstack((a, np.full((160, 180), 255, np.uint8)))
    path = tmp_path/f"{noisy}-{weaken}-{alpha}.png"
    Image.fromarray(a).save(path)
    return path


FLAT = (12, 20, 48, 70)
EDGE = (82, 25, 25, 105)


def test_detects_excess_grain_inside_ink_fill(tmp_path):
    old, new = fixture(tmp_path, noisy=5), fixture(tmp_path, noisy=13)
    result = probe.compare(old, new, FLAT, EDGE)
    assert result["automated_check"] == "POSSIBLE_REGRESSION"
    assert any("noise increased" in s for s in result["warnings"])
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_smoother_fill_cannot_claim_print_certification(tmp_path):
    old, new = fixture(tmp_path, noisy=12), fixture(tmp_path, noisy=4)
    result = probe.compare(old, new, FLAT, EDGE)
    assert result["automated_check"] == "NO_AUTOMATED_REGRESSION_DETECTED"
    assert result["measurements"]["flat"]["v21"] < result["measurements"]["flat"]["v2"]
    assert result["print_certification"] == "NOT_CERTIFIED"


def test_detects_softened_letter_edges(tmp_path):
    old = fixture(tmp_path, noisy=4)
    new = fixture(tmp_path, noisy=4, weaken=True)
    result = probe.compare(old, new, FLAT, EDGE)
    assert result["automated_check"] == "POSSIBLE_REGRESSION"
    assert any("edge strength" in s for s in result["warnings"])


def test_detects_alpha_loss(tmp_path):
    old = fixture(tmp_path, noisy=7, alpha=True)
    new = tmp_path/"candidate.png"
    a = np.asarray(Image.open(old)).copy()
    a[:, 90:100, 3] = 120
    Image.fromarray(a).save(new)
    result = probe.compare(old, new, FLAT, EDGE)
    assert result["automated_check"] == "POSSIBLE_REGRESSION"
    assert any("alpha plane" in s for s in result["warnings"])


def test_mismatched_image_size_never_claims_success(tmp_path):
    old = fixture(tmp_path, noisy=3)
    new = tmp_path/"different.png"
    Image.new("RGB", (161, 180), "white").save(new)
    result = probe.compare(old, new, FLAT, EDGE)
    assert result["automated_check"] == "NOT_TESTED"


def test_large_output_without_pyvips_never_decodes_full_image(tmp_path, monkeypatch):
    old, new = fixture(tmp_path, noisy=3), fixture(tmp_path, noisy=6)
    monkeypatch.setattr(probe, "MAX_FULL_IMAGE_PIXELS", 1)
    import sys
    monkeypatch.setitem(sys.modules, "pyvips", None)
    assert probe.compare(old, new, FLAT, EDGE)["automated_check"] == "NOT_TESTED"


def test_cli_writes_not_certified_report(tmp_path):
    old, new = fixture(tmp_path, noisy=12), fixture(tmp_path, noisy=4)
    report = tmp_path/"result.json"
    assert probe.main([
        str(old), str(new), "--flat-roi", "12,20,48,70",
        "--edge-roi", "82,25,25,105", "--report", str(report)
    ]) == 0
    assert "NOT_CERTIFIED" in report.read_text()
