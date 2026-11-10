"""End-to-end smoke test for four-engine runner using local fake executables.

This tests wiring and image validation only; it does not claim real AI inference.
"""
import json
import sys
import zlib
from pathlib import Path

import pytest

from PIL import Image, ImageCms, ImageDraw

from tools.v211_four_engine_run import (
    run, _privacy_safe_report, _safe_error_summary,
)
from tools.v211_four_engine_coordinator import run_candidates
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand
from tools import v211_four_engine_run as runner


def _minimal_png_ihdr(width, height, color_type=2):
    payload = (
        width.to_bytes(4, "big") + height.to_bytes(4, "big")
        + bytes((8, color_type, 0, 0, 0))
    )
    chunk = b"IHDR" + payload
    return (
        b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big")
        + chunk + (zlib.crc32(chunk) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def test_four_engine_runner_produces_four_valid_candidates(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    code = (
        "import sys; from PIL import Image; "
        "im=Image.open(sys.argv[1]); im.save(sys.argv[2])"
    )
    config = tmp_path / "engines.json"
    commands = {}
    for name in ENGINES:
        device_args = (
            ["-g", "0"] if name in ("real_esrgan", "waifu2x", "real_cugan")
            else ["-p", "cuda", "-d", "0"]
        )
        commands[name] = [
            sys.executable, "-c", code, "{input}", "{output}", *device_args
        ]
    config.write_text(json.dumps(commands), encoding="utf-8")
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert result["ready_for_fusion_research"]
    assert not result["fusion_implemented"]
    assert not result["quality_certified"]
    assert set(result["candidates"]) == set(ENGINES)
    assert not result["failures"]
    assert result["runtime_device_use_verified"] is False
    assert "physical adapter use" in result["execution_evidence_scope"]
    assert set(result["engine_execution"]) == set(ENGINES)
    for name, evidence in result["engine_execution"].items():
        process = evidence["process"]
        assert process["status"] == "output_ready"
        assert process["process_started"] is True
        assert isinstance(process["pid"], int) and process["pid"] > 0
        assert process["exit_code"] == 0
        assert process["process_elapsed_ms"] >= 0
        assert evidence["runtime_device_use_verified"] is False
        assert evidence["device_configuration"]["explicitly_configured"] is True
        assert evidence["device_configuration"]["actual_adapter_verified"] is False
        assert not ({"argv", "stdout", "stderr", "source", "destination"} & set(process))
    assert result["engine_execution"]["real_esrgan"]["device_configuration"] == {
        "backend": "ncnn_vulkan", "device_index": 0,
        "explicitly_configured": True, "actual_adapter_verified": False,
    }
    assert result["engine_execution"]["anime4k"]["device_configuration"] == {
        "backend": "cuda", "device_index": 0,
        "explicitly_configured": True, "actual_adapter_verified": False,
    }
    for output in result["candidates"].values():
        with Image.open(output) as image:
            assert image.size == (8, 8)
            assert image.mode == "RGB"
    report = json.loads((tmp_path / "outputs" / "four_engine_report.json").read_text(encoding="utf-8"))
    assert report["ready_for_fusion_research"]



def test_small_rgba_runner_rebinds_candidates_to_exact_v2_alpha(tmp_path):
    """Small native jobs must use V2's exact alpha, not a seed down/up round-trip."""
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    reference = Image.new("RGBA", (32, 32), (180, 80, 60, 255))
    reference_alpha = Image.new("L", (32, 32), 0)
    draw = ImageDraw.Draw(reference_alpha)
    for y in range(0, 32, 4):
        for x in range(0, 32, 4):
            if ((x // 4) + (y // 4)) % 2 == 0:
                draw.rectangle((x, y, x + 3, y + 3), fill=255)
    reference.putalpha(reference_alpha)
    v2_reference = tmp_path / "accepted-v2-rgba.png"
    reference.save(v2_reference, dpi=(300, 300), icc_profile=profile)

    source = Image.new("RGBA", (16, 16), (70, 110, 150, 255))
    source.putalpha(reference_alpha.resize((16, 16), Image.Resampling.LANCZOS))
    source_path = tmp_path / "native-seed-rgba.png"
    source.save(source_path, dpi=(300, 300), icc_profile=profile)

    # This fake CLI models the native wrapper's 2x output. The subprocess
    # adapter restores seed alpha; the runner must then rebind it to exact V2.
    code = (
        "import sys; from PIL import Image; "
        "im=Image.open(sys.argv[1]); "
        "out=im.resize((im.width*2, im.height*2), Image.Resampling.LANCZOS); "
        "out.save(sys.argv[2], format='PNG', "
        "icc_profile=im.info.get('icc_profile'), dpi=im.info.get('dpi'))"
    )
    config = tmp_path / "rgba-engines.json"
    commands = {
        name: [sys.executable, "-c", code, "{input}", "{output}"]
        for name in ENGINES
    }
    config.write_text(json.dumps(commands), encoding="utf-8")

    report = run(
        source_path,
        tmp_path / "rgba-output",
        config,
        (32, 32),
        real_engines=False,
        v2_reference=v2_reference,
    )

    assert report["completed_engine_count"] == 4
    assert report["fusion_implemented"] is True
    assert "fusion_error" not in report
    with Image.open(v2_reference) as accepted_v2:
        expected_alpha = accepted_v2.getchannel("A").tobytes()
        expected_icc = accepted_v2.info.get("icc_profile")
        expected_dpi = accepted_v2.info.get("dpi")
    for candidate_path in report["candidates"].values():
        with Image.open(candidate_path) as candidate:
            assert candidate.mode == "RGBA"
            assert candidate.getchannel("A").tobytes() == expected_alpha
            assert candidate.info.get("icc_profile") == expected_icc
            assert candidate.info.get("dpi") == expected_dpi

    fused_path = Path(report["four_engine_fusion"]["output"])
    with Image.open(fused_path) as fused:
        assert fused.mode == "RGBA"
        assert fused.getchannel("A").tobytes() == expected_alpha
        assert fused.info.get("icc_profile") == expected_icc
        assert fused.info.get("dpi") == expected_dpi



def test_runner_reports_failed_engine(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8)).save(source)
    code = "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])"
    config = tmp_path / "engines.json"
    commands = {
        name: [sys.executable, "-c", code, "{input}", "{output}"]
        for name in ENGINES
    }
    commands["anime4k"] = [
        sys.executable, "-c",
        "import sys;print(sys.argv[1], file=sys.stderr);sys.exit(4)",
        "{input}", "{output}",
    ]
    config.write_text(json.dumps(commands), encoding="utf-8")
    result = run(source, tmp_path / "outputs", config, (8, 8), real_engines=False)
    assert not result["ready_for_fusion_research"]
    assert "anime4k" in result["failures"]
    assert len(result["candidates"]) == 3
    execution = result["engine_execution"]
    assert execution["anime4k"]["process"]["status"] == "process_failed"
    assert execution["anime4k"]["process"]["process_started"] is True
    assert execution["anime4k"]["process"]["exit_code"] == 4
    assert all(
        execution[name]["process"]["status"] == "output_ready"
        for name in ENGINES if name != "anime4k"
    )
    assert result["real_engine_inference_proven"] is False
    assert result["failures"]["anime4k"]["details_redacted"] is True
    assert result["failures"]["anime4k"]["error_type"] == "RuntimeError"
    persisted = (tmp_path / "outputs" / "four_engine_report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in persisted
    assert "stderr" not in persisted
    assert "candidate_files" in json.loads(persisted)
    assert "candidates" not in json.loads(persisted)


def test_privacy_safe_report_redacts_nested_output_paths(tmp_path):
    report = {
        "candidates": {"real_esrgan": str(tmp_path / "engine" / "real_esrgan.png")},
        "failures": {"waifu2x": "RuntimeError: private stderr " + str(tmp_path)},
        "three_engine_priority_preview": {
            "selected": "real_esrgan",
            "output": str(tmp_path / "preview.png"),
        },
        "four_engine_fusion": {
            "fusion_implemented": True,
            "output": str(tmp_path / "fused.png"),
        },
        "fusion_error": "OSError: " + str(tmp_path / "private"),
    }
    safe = _privacy_safe_report(report)
    serialized = json.dumps(safe)
    assert str(tmp_path) not in serialized
    assert "private stderr" not in serialized
    assert safe["candidate_files"] == {"real_esrgan": "real_esrgan.png"}
    assert safe["three_engine_priority_preview"]["output_filename"] == "preview.png"
    assert safe["four_engine_fusion"]["output_filename"] == "fused.png"
    assert safe["fusion_error"]["details_redacted"] is True


def test_safe_error_summary_does_not_trust_redaction_marker(tmp_path):
    private_path = str(tmp_path / "customer-artwork.png")
    supplied = {
        "details_redacted": True,
        "error_type": "RuntimeError",
        "error_class": "engine_failed",
        "stderr": "failed while opening " + private_path,
        "path": private_path,
        "argv": ["native-engine.exe", private_path],
        "extra": {"customer_file": private_path},
    }

    safe = _safe_error_summary(supplied)

    assert safe == {
        "error_type": "RuntimeError",
        "error_class": "engine_failed",
        "details_redacted": True,
    }
    assert private_path not in json.dumps(safe)

    malformed = {
        "details_redacted": True,
        "error_type": private_path,
        "error_class": private_path,
        "stderr": private_path,
    }
    assert _safe_error_summary(malformed) == {
        "error_type": "EngineError",
        "error_class": "engine_failed",
        "details_redacted": True,
    }


def test_coordinator_cancellation_removes_already_completed_candidate_files(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    output_dir = tmp_path / "cancelled-output"
    calls = []

    def processor(src, destination):
        calls.append(destination.name)
        with Image.open(src) as image:
            image.save(destination)

    processors = {name: processor for name in ENGINES}

    with pytest.raises(InterruptedError, match="stopped"):
        run_candidates(
            source, output_dir, (8, 8), processors,
            cancel_check=lambda: bool(calls),
        )

    assert calls == ["real_esrgan.png"]
    assert not list(output_dir.glob("*.png"))


def test_runner_fails_closed_above_18mp_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    # A missing manifest proves the size guard runs before model provisioning
    # or any native executable is inspected/launched.
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(RuntimeError, match="above 18 MP"):
        run(source, output_dir, config, (6_000, 4_000), real_engines=True)

    assert not output_dir.exists()
    assert not config.exists()



def test_runner_rejects_oversized_v2_reference_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    large_reference = tmp_path / "large-v2-reference.png"
    ihdr = (
        (6_000).to_bytes(4, "big") + (4_000).to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    chunk = b"IHDR" + ihdr
    large_reference.write_bytes(
        b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big")
        + chunk + (zlib.crc32(chunk) & 0xFFFFFFFF).to_bytes(4, "big")
    )
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="V2 reference dimensions"):
        run(
            source, output_dir, config, (8, 8),
            real_engines=True, v2_reference=large_reference,
        )

    assert not output_dir.exists()
    assert not config.exists()
    assert large_reference.stat().st_size == 33


def test_runner_rejects_v2_reference_geometry_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    reference = tmp_path / "wrong-size-v2.png"
    Image.new("RGB", (4, 4), (20, 80, 120)).save(reference)
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="V2 reference dimensions"):
        run(
            source, output_dir, config, (8, 8),
            real_engines=True, v2_reference=reference,
        )

    assert not output_dir.exists()
    assert not config.exists()



def test_runner_rejects_corrupt_source_png_ihdr_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "corrupt-source.png"
    header = bytearray(_minimal_png_ihdr(8, 8))
    header[-1] ^= 0x01
    source.write_bytes(header)
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="IHDR checksum"):
        run(source, output_dir, config, (16, 16), real_engines=True)

    assert not output_dir.exists()
    assert not config.exists()


def test_runner_rejects_unsupported_source_mode_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "palette-source.png"
    Image.new("P", (8, 8)).save(source)
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="RGB or RGBA"):
        run(source, output_dir, config, (16, 16), real_engines=True)

    assert not output_dir.exists()
    assert not config.exists()


def test_runner_rejects_v2_reference_mode_mismatch_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "source.png"
    reference = tmp_path / "v2-reference.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    Image.new("RGBA", (16, 16), (20, 80, 120, 255)).save(reference)
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="mode differs"):
        run(
            source, output_dir, config, (16, 16),
            real_engines=True, v2_reference=reference,
        )

    assert not output_dir.exists()
    assert not config.exists()


def test_runner_rejects_v2_reference_icc_mismatch_before_manifest_or_native_launch(tmp_path):
    source = tmp_path / "source.png"
    reference = tmp_path / "v2-reference.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(
        source, icc_profile=b"source-icc-profile"
    )
    Image.new("RGB", (16, 16), (20, 80, 120)).save(
        reference, icc_profile=b"different-v2-icc-profile"
    )
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="ICC differs"):
        run(
            source, output_dir, config, (16, 16),
            real_engines=True, v2_reference=reference,
        )

    assert not output_dir.exists()
    assert not config.exists()



@pytest.mark.parametrize("target_size", [(24,  24), (64, 64), (16, 32)])
def test_runner_rejects_unsupported_fusion_scale_before_manifest_or_native_launch(
    tmp_path, target_size
):
    """3x, 8x and anisotropic targets must fail before expensive native inference."""
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    reference = tmp_path / "v2-reference.png"
    Image.new("RGB", target_size, (20, 80, 120)).save(reference)
    config = tmp_path / "manifest-must-not-be-read.json"
    output_dir = tmp_path / "must-not-be-created"

    with pytest.raises(ValueError, match="exact 2x or 4x"):
        run(
            source, output_dir, config, target_size,
            real_engines=True, v2_reference=reference,
        )

    assert not output_dir.exists()
    assert not config.exists()


def test_runner_uses_disk_backed_native_tiles_for_large_png_jobs(tmp_path, monkeypatch):
    pytest.importorskip("pyvips")
    from tools import v211_four_engine_run as runner

    monkeypatch.setattr(runner, "MAX_FOUR_ENGINE_PIXELS", 1)
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "tile-source.png"
    Image.new("RGB", (64, 64), (25, 70, 115)).save(
        source, dpi=(300, 300), icc_profile=profile
    )
    with Image.open(source) as image:
        reference_image = image.resize((128, 128), Image.Resampling.NEAREST)
        reference = tmp_path / "accepted-v2.png"
        reference_image.save(reference, dpi=(300, 300), icc_profile=profile)
        reference_image.close()

    script = (
        "import sys; from PIL import Image; "
        "im=Image.open(sys.argv[1]); "
        "out=im.resize((im.width*2, im.height*2), Image.Resampling.NEAREST); "
        "out.save(sys.argv[2], format='PNG', "
        "icc_profile=im.info.get('icc_profile'), dpi=im.info.get('dpi'))"
    )
    config = tmp_path / "research-commands.json"
    commands = {
        name: [sys.executable, "-c", script, "{input}", "{output}"]
        for name in ENGINES
    }
    config.write_text(json.dumps(commands), encoding="utf-8")
    before = reference.read_bytes()

    report = runner.run(
        source, tmp_path / "tiled-run", config, (128, 128),
        real_engines=False, v2_reference=reference,
    )

    assert report["native_tiled_inference"]["implemented"] is True
    assert report["native_tiled_inference"]["all_four_engines_completed"] is True
    assert report["completed_engine_count"] == 4
    for name in ENGINES:
        process = report["engine_execution"][name]["process"]
        assert process["tile_count"] == 1
        assert process["tile_process_count"] == 1
        assert process["tile_process_scope"] == "all_tiles_aggregated"
        assert process["tile_process_elapsed_ms_total"] >= 0
    assert report["fusion_implemented"] is True
    assert report["quality_certified"] is False
    assert report["three_engine_priority_preview"]["status"] == "skipped_large_tiled_job"
    assert reference.read_bytes() == before
    assert (tmp_path / "tiled-run" / "four_engine_fused_preview.png").is_file()
    persisted = json.loads(
        (tmp_path / "tiled-run" / "four_engine_report.json").read_text(encoding="utf-8")
    )
    assert persisted["native_tiled_inference"]["gpu_adapter_verified"] is False
    assert str(tmp_path) not in json.dumps(persisted)


def _write_large_header_png(path, width, height, *, rgba=False, icc=b"large-synthetic-icc"):
    def chunk(kind, payload):
        checksum = zlib.crc32(kind)
        checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
        return (
            len(payload).to_bytes(4, "big") + kind + payload
            + checksum.to_bytes(4, "big")
        )

    color_type = 6 if rgba else 2
    ihdr = (
        width.to_bytes(4, "big") + height.to_bytes(4, "big")
        + bytes((8, color_type, 0, 0, 0))
    )
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"iCCP", b"NiyomSilp ICC\x00\x00" + zlib.compress(icc))
        + (0).to_bytes(4, "big") + b"IDAT"
    )
    return path


def test_runner_routes_200mp_seed_and_800mp_v2_header_to_disk_tiles_without_pillow(
    tmp_path, monkeypatch
):
    """Header preflight must not hit Pillow's ~178 MP hard decompression ceiling."""
    from tools import v211_four_engine_run as runner
    from tools.v211_four_engine_subprocess import EngineCommand

    source = _write_large_header_png(tmp_path / "200mp-seed.png", 20_000, 10_000)
    reference = _write_large_header_png(tmp_path / "800mp-v2.png", 40_000, 20_000)
    commands = {
        name: EngineCommand(
            ("fake-engine.exe", "{input}", "{output}", "-g", "0")
            if name != "anime4k"
            else ("fake-anime4k.exe", "{input}", "{output}", "-p", "cuda", "-d", "0")
        )
        for name in ENGINES
    }
    monkeypatch.setattr(runner, "load_real_engine_manifest", lambda _path: commands)
    monkeypatch.setattr(
        runner, "make_processors",
        lambda *_args, **_kwargs: {name: (lambda *_a, **_k: None) for name in ENGINES},
    )
    calls = []

    def fake_tiled(source_path, reference_path, output_dir, size, processors, **kwargs):
        calls.append((source_path, reference_path, tuple(size), set(processors)))
        return {
            "candidates": [],
            "failures": {},
            "ready_for_fusion_research": False,
            "native_tiled_inference": {"implemented": True},
        }

    monkeypatch.setattr(runner, "run_tiled_candidates", fake_tiled)

    def reject_pillow(*_args, **_kwargs):
        raise AssertionError("large PNG metadata preflight must not call Pillow Image.open")

    monkeypatch.setattr(runner.Image, "open", reject_pillow)
    result = runner.run(
        source, tmp_path / "large-run", tmp_path / "verified-manifest.json",
        (40_000, 20_000), real_engines=True, v2_reference=reference,
    )

    assert calls == [(source, reference, (40_000, 20_000), set(ENGINES))]
    assert result["native_tiled_inference"]["implemented"] is True
    assert result["completed_engine_count"] == 0
    assert result["quality_certified"] is False
    assert (tmp_path / "large-run" / "four_engine_report.json").is_file()



def test_real_engine_runner_withholds_fusion_without_runtime_gpu_proof(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.png"
    reference = tmp_path / "accepted-v2.png"
    output_dir = tmp_path / "out"
    Image.new("RGB", (8, 8), (20, 80, 120)).save(source)
    Image.new("RGB", (16, 16), (20, 80, 120)).save(reference)

    commands = {
        name: EngineCommand((
            "fake-" + name, "-i", "{input}", "-o", "{output}",
        ))
        for name in ENGINES
    }
    monkeypatch.setattr(runner, "load_real_engine_manifest", lambda _path: commands)

    def resize_processor(input_path, output_path):
        with Image.open(input_path) as image:
            metadata = {
                key: image.info[key]
                for key in ("icc_profile", "dpi")
                if key in image.info
            }
            image.resize(
                (image.width * 2, image.height * 2),
                resample=Image.Resampling.NEAREST,
            ).save(output_path, format="PNG", **metadata)

    monkeypatch.setattr(
        runner,
        "make_processors",
        lambda _commands, cancel_check=None, pre_launch_check=None,
               execution_records=None, runtime_device_probe=None:
            {name: resize_processor for name in ENGINES},
    )
    monkeypatch.setattr(
        runner,
        "fuse_four_engine_details",
        lambda *args, **kwargs: pytest.fail(
            "real-engine fusion must not run without verified runtime GPU use"
        ),
    )

    result = runner.run(
        source,
        output_dir,
        tmp_path / "verified-manifest.json",
        (16, 16),
        real_engines=True,
        v2_reference=reference,
    )

    assert result["completed_engine_count"] == 4
    assert result["runtime_device_use_verified"] is False
    assert result["ready_for_fusion_research"] is False
    assert result["fusion_block_reason"] == "gpu_runtime_unverified"
    assert result["per_engine_runtime_device_use_verified"] == {
        name: False for name in ENGINES
    }
    assert not (output_dir / "four_engine_fused_preview.png").exists()
