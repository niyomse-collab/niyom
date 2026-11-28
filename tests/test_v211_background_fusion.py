"""Synthetic integration contract for automatic four-engine V2 raster enhancement.

These tests mock native inference; they never claim actual four-model GPU QA.
"""
from pathlib import Path

import numpy as np
from PIL import Image

from signprint_ai import v211_background_fusion as background
from tools import v211_four_engine_run


def _base_and_source(tmp_path, rgba=False):
    mode = "RGBA" if rgba else "RGB"
    source = tmp_path / ("source.tif" if rgba else "source.jpg")
    Image.new(mode, (7, 5), (40, 90, 120, 220) if rgba else (40, 90, 120)).save(source)
    base = Image.new(mode, (15, 11), (40, 90, 120, 220) if rgba else (40, 90, 120))
    base.info["dpi"] = (300, 300)
    return source, base


def test_missing_manifest_keeps_v2_pixel_exact(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    monkeypatch.setattr(background, "default_manifest", lambda: tmp_path / "missing.json")
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original and output.tobytes() == snapshot
    assert report["status"] == "models_not_installed"
    assert report["four_engines_applied"] is False


def test_four_engine_candidate_never_replaces_accepted_v2_export_raster(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    calls = []

    def fake_native_run(seed, output_dir, config, size, **kwargs):
        calls.append((Path(seed), config, size, kwargs))
        assert size == (16, 12)  # odd custom V2 output size is edge padded.
        with Image.open(seed) as seed_image:
            assert seed_image.size == (8, 6)
            assert seed_image.mode == "RGBA"
        with Image.open(kwargs["v2_reference"]) as image:
            modified = np.asarray(image).copy()
        modified[0, 0, 0] += 4
        output_dir.mkdir(parents=True)
        fused = output_dir / "four_engine_fused_preview.png"
        Image.fromarray(modified, "RGBA").save(fused)
        return {
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "output": str(fused),
                "engine_detail_contribution_mean_abs": {
                    name: 0.1 for name in
                    ("real_esrgan", "waifu2x", "real_cugan", "anime4k")
                },
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", fake_native_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert report["status"] == "four_engine_candidate_not_promoted"
    assert report["four_engines_applied"] is False
    assert report["v2_output_preserved"] is True
    assert report["quality_certified"] is False
    assert report["completed_engine_count"] == 4
    assert len(calls) == 1
    assert calls[0][3]["real_engines"] is True
    assert output.size == original.size == (15, 11)
    assert output.mode == original.mode == "RGBA"
    assert output.getchannel("A").tobytes() == original.getchannel("A").tobytes()
    assert output.info["dpi"] == original.info["dpi"]
    assert output is original
    assert output.tobytes() == snapshot
    assert original.tobytes() == snapshot  # V2 reference never mutated.
    assert not list(tmp_path.glob("*V211-4AI-QA*"))


def test_incomplete_real_engine_run_never_modifies_print_raster(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)

    def partial_run(*args, **kwargs):
        return {"completed_engine_count": 3, "failures": {"anime4k": "missing"},
                "four_engine_fusion": {}}

    monkeypatch.setattr(v211_four_engine_run, "run", partial_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original
    assert report["four_engines_applied"] is False
    assert report["status"] == "four_engine_incomplete"
    assert report["failures"]["anime4k"] == "missing"


def test_large_image_fallback_reports_ineligible_instead_of_claiming_four_ai(tmp_path, monkeypatch):
    source, _ = _base_and_source(tmp_path)
    monkeypatch.setattr(background, "_MAX_IN_MEMORY_PIXELS", 100)
    output = Image.new("RGB", (15, 11), "navy")
    result, report = background.maybe_enhance_v2_image(source, output)
    assert result is output
    assert report["status"] == "large_image_tiling_pending"
    assert report["four_engines_applied"] is False


def test_disabled_four_ai_never_changes_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path)
    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "0")
    result, report = background.maybe_enhance_v2_image(source, original)
    assert result is original and report["status"] == "disabled"


def test_native_runner_exception_preserves_v2_and_reports_failure(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def failing_run(*args, **kwargs):
        raise RuntimeError("native engine failed")

    monkeypatch.setattr(v211_four_engine_run, "run", failing_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original
    assert output.tobytes() == snapshot
    assert report["status"] == "four_engine_error"
    assert report["v2_output_preserved"] is True
    assert report["four_engines_applied"] is False
    assert report["error"].startswith("RuntimeError:")


def test_cancel_before_native_work_preserves_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    try:
        background.maybe_enhance_v2_image(source, original, cancel=lambda: True)
    except InterruptedError:
        pass
    else:
        raise AssertionError("Cancellation must propagate, not silently fall back")
    assert original.tobytes() == snapshot


def test_cancel_after_successful_native_fusion_never_promotes_candidate(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)
    cancel_checks = []

    def cancel():
        cancel_checks.append(True)
        return len(cancel_checks) >= 2

    def successful_run(seed, output_dir, config, size, **kwargs):
        output_dir.mkdir(parents=True)
        with Image.open(kwargs["v2_reference"]) as image:
            modified = np.asarray(image).copy()
        modified[0, 0, 0] += 1
        fused = output_dir / "fused.png"
        Image.fromarray(modified, "RGBA").save(fused)
        return {
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {"fusion_implemented": True, "output": str(fused)},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", successful_run)
    try:
        background.maybe_enhance_v2_image(source, original, cancel=cancel)
    except InterruptedError:
        pass
    else:
        raise AssertionError("Late cancellation must propagate after native fusion")
    assert len(cancel_checks) == 2
    assert original.tobytes() == snapshot
    assert not list(tmp_path.glob("*V211-4AI-QA*"))


def test_native_fusion_alpha_mismatch_fails_closed_without_v2_mutation(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def invalid_alpha_run(seed, output_dir, config, size, **kwargs):
        output_dir.mkdir(parents=True)
        with Image.open(kwargs["v2_reference"]) as image:
            modified = np.asarray(image).copy()
        modified[0, 0, 3] = 0
        fused = output_dir / "invalid_alpha.png"
        Image.fromarray(modified, "RGBA").save(fused)
        return {
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {"fusion_implemented": True, "output": str(fused)},
        }

    monkeypatch.setattr(v211_four_engine_run, "run", invalid_alpha_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original
    assert original.tobytes() == snapshot
    assert report["status"] == "four_engine_error"
    assert report["v2_output_preserved"] is True
    assert report["four_engines_applied"] is False
    assert report["error"].startswith("ValueError:")


def test_four_engine_identical_candidate_reports_no_effect_and_keeps_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def unchanged_run(seed, output_dir, config, size, **kwargs):
        output_dir.mkdir(parents=True)
        candidate = output_dir / "unchanged.png"
        with Image.open(kwargs["v2_reference"]) as reference:
            reference.save(candidate)
        return {
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True, "output": str(candidate)
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", unchanged_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original
    assert original.tobytes() == snapshot
    assert report["status"] == "four_engine_no_pixel_effect"
    assert report["completed_engine_count"] == 4
    assert report["four_engines_applied"] is False
    assert report["v2_output_preserved"] is True
    assert not list(tmp_path.glob("*V211-4AI-QA*"))


def test_missing_fusion_output_fails_closed_without_mutating_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def missing_output_run(seed, output_dir, config, size, **kwargs):
        return {
            "completed_engine_count": 4,
            "failures": {},
            "four_engine_fusion": {
                "fusion_implemented": True,
                "output": str(output_dir / "does-not-exist.png"),
            },
        }

    monkeypatch.setattr(v211_four_engine_run, "run", missing_output_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original
    assert original.tobytes() == snapshot
    assert report["status"] == "four_engine_error"
    assert report["four_engines_applied"] is False
    assert report["v2_output_preserved"] is True
    assert not list(tmp_path.glob("*V211-4AI-QA*"))


def test_fusion_wrong_mode_fails_closed_and_preserves_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path, rgba=True)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def wrong_mode_run(seed, output_dir, config, size, **kwargs):
        output_dir.mkdir(parents=True)
        fused = output_dir / "rgb_without_alpha.png"
        Image.new("RGB", size, (40, 90, 120)).save(fused)
        return {"completed_engine_count": 4, "failures": {},
                "four_engine_fusion": {"fusion_implemented": True, "output": str(fused)}}

    monkeypatch.setattr(v211_four_engine_run, "run", wrong_mode_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original and original.tobytes() == snapshot
    assert report["status"] == "four_engine_error"
    assert report["v2_output_preserved"] is True
    assert report["four_engines_applied"] is False
    assert report["error"].startswith("ValueError:")


def test_fusion_undersized_output_fails_closed_and_preserves_v2(tmp_path, monkeypatch):
    source, original = _base_and_source(tmp_path)
    snapshot = original.tobytes()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("test-only", encoding="utf8")
    monkeypatch.setattr(background, "default_manifest", lambda: manifest)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_MANIFEST", raising=False)
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI", raising=False)

    def undersized_run(seed, output_dir, config, size, **kwargs):
        output_dir.mkdir(parents=True)
        fused = output_dir / "undersized.png"
        Image.new("RGB", (size[0] - 2, size[1] - 2), (40, 90, 120)).save(fused)
        return {"completed_engine_count": 4, "failures": {},
                "four_engine_fusion": {"fusion_implemented": True, "output": str(fused)}}

    monkeypatch.setattr(v211_four_engine_run, "run", undersized_run)
    output, report = background.maybe_enhance_v2_image(source, original)
    assert output is original and original.tobytes() == snapshot
    assert report["status"] == "four_engine_error"
    assert report["v2_output_preserved"] is True
    assert report["four_engines_applied"] is False
    assert report["error"].startswith("ValueError:")
