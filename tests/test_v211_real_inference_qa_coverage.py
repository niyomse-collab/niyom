"""Exercise real-inference QA evidence logic without claiming real AI ran."""
import json

import pytest
from PIL import Image

from tools import v211_four_engine_real_inference_qa as qa
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand


def _source(tmp_path, rgba=False, *, dpi=True):
    src = tmp_path / "artwork.png"
    mode = "RGBA" if rgba else "RGB"
    color = (20, 80, 120, 97) if rgba else (20, 80, 120)
    options = {"dpi": (300, 300)} if dpi else {}
    Image.new(mode, (24, 16), color).save(src, **options)
    return src


def _prepare(
    monkeypatch, *, failed_engine=None, wrong_geometry=None,
    failure_message=None, failure_exit_code=1,
):
    calls = []

    def factory(_manifest, *, execution_records=None):
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination, *, engine=name):
                calls.append(engine)
                if execution_records is not None:
                    execution_records[engine] = {
                        "status": "process_failed" if engine == failed_engine else "output_ready",
                        "process_started": True,
                        "pid": 12000 + list(ENGINES).index(engine),
                        "exit_code": failure_exit_code if engine == failed_engine else 0,
                        "process_elapsed_ms": 12,
                        "elapsed_ms_total": 15,
                    }
                if engine == failed_engine:
                    raise RuntimeError(failure_message or "simulated subprocess failure")
                with Image.open(source) as image:
                    size = (48, 32) if engine != wrong_geometry else (47, 32)
                    resampled = image.resize(size, Image.Resampling.LANCZOS)
                    resampled.save(destination, dpi=(300, 300))
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(qa, "load_real_engine_manifest", lambda *_: {"test": "fake manifest"})
    monkeypatch.setattr(qa, "make_processors", factory)
    return calls


def test_all_four_candidates_valid_no_visual_certification(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch)
    source = _source(tmp_path)
    result = qa.run(tmp_path / "manifest.json", source, tmp_path / "outputs")
    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is True
    assert result["quality_improvement_verified"] is False
    assert result["completed_engine_count"] == 4
    assert result["candidate_output_validation_complete"] is True
    assert result["native_process_execution_verified"] is True
    assert result["per_engine_native_process_execution_verified"] == {
        name: True for name in ENGINES
    }
    assert not result["failures"]
    assert result["runtime_device_use_verified"] is False
    assert result["engines"]["real_esrgan"]["process"]["exit_code"] == 0
    assert result["engines"]["real_esrgan"]["process"]["pid"] == 12000
    assert result["engines"]["real_esrgan"]["device_configuration"] is None
    assert json.loads((tmp_path / "outputs" / "real_inference_report.json").read_text())["completed_engine_count"] == 4



def test_valid_candidate_outputs_without_native_process_evidence_do_not_certify_inference(
    tmp_path, monkeypatch
):
    def factory(_manifest):
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination):
                with Image.open(source) as image:
                    image.resize(
                        (image.width * 2, image.height * 2),
                        Image.Resampling.LANCZOS,
                    ).save(destination, dpi=(300, 300))
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(
        qa, "load_real_engine_manifest", lambda *_: {"test": "fake manifest"}
    )
    monkeypatch.setattr(qa, "make_processors", factory)
    result = qa.run(
        tmp_path / "manifest.json",
        _source(tmp_path),
        tmp_path / "outputs-without-process-evidence",
    )

    assert result["completed_engine_count"] == 4
    assert result["candidate_output_validation_complete"] is True
    assert result["native_process_execution_verified"] is False
    assert result["per_engine_native_process_execution_verified"] == {
        name: False for name in ENGINES
    }
    assert result["real_inference_verified"] is False
    assert result["quality_improvement_verified"] is False

def test_one_failure_does_not_hide_other_three_engine_results(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch, failed_engine="real_esrgan")
    source = _source(tmp_path)
    result = qa.run(tmp_path / "manifest.json", source, tmp_path / "outputs")
    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is False
    assert result["completed_engine_count"] == 3
    assert set(result["failures"]) == {"real_esrgan"}
    assert result["failures"]["real_esrgan"]["process"]["exit_code"] == 1
    assert (tmp_path / "outputs" / "anime4k.png").is_file()


def test_wrong_geometry_is_not_inference_success(tmp_path, monkeypatch):
    calls = _prepare(monkeypatch, wrong_geometry="anime4k")
    result = qa.run(tmp_path / "manifest.json", _source(tmp_path), tmp_path / "out")
    assert calls == list(ENGINES)
    assert result["completed_engine_count"] == 3
    assert result["real_inference_verified"] is False
    assert "anime4k" in result["failures"]


def test_alpha_image_qa_uses_original_cutout(tmp_path, monkeypatch):
    _prepare(monkeypatch)
    result = qa.run(tmp_path / "manifest.json", _source(tmp_path, rgba=True), tmp_path / "out")
    assert result["real_inference_verified"] is True
    assert result["engines"]["anime4k"]["alpha_preserved"] is True


def test_device_configuration_reports_cli_flags_without_claiming_actual_adapter():
    from tools.v211_four_engine_subprocess import EngineCommand

    ncnn = EngineCommand((
        "realesrgan.exe", "-i", "{input}", "-o", "{output}", "-g", "2"
    ))
    anime = EngineCommand((
        "ac_cli.exe", "-i", "{input}", "-o", "{output}", "-p", "cuda", "-d", "0"
    ))
    assert qa._configured_device_selection("real_esrgan", ncnn) == {
        "backend": "ncnn_vulkan",
        "device_index": 2,
        "explicitly_configured": True,
        "actual_adapter_verified": False,
    }
    assert qa._configured_device_selection("anime4k", anime) == {
        "backend": "cuda",
        "device_index": 0,
        "explicitly_configured": True,
        "actual_adapter_verified": False,
    }


def test_process_telemetry_report_omits_paths_and_raw_output(tmp_path, monkeypatch):
    _prepare(monkeypatch)
    source = _source(tmp_path)
    result = qa.run(tmp_path / "manifest.json", source, tmp_path / "private-report")
    payload = json.dumps(result)
    assert str(tmp_path) not in payload
    assert '"argv"' not in payload
    assert '"stdout"' not in payload
    assert '"stderr"' not in payload
    assert result["runtime_device_use_verified"] is False



def test_preflight_fail_does_not_claim_execution(tmp_path, monkeypatch):
    def bad(_manifest):
        raise ValueError("bad model hashes")
    monkeypatch.setattr(qa, "load_real_engine_manifest", bad)
    with pytest.raises(ValueError):
        qa.run(tmp_path / "manifest.json", _source(tmp_path), tmp_path / "out")
    report = json.loads((tmp_path / "out" / "real_inference_report.json").read_text())
    assert report["real_inference_verified"] is False
    assert report["failed_stage"] == "manifest_preflight"



def test_timeout_override_caps_each_native_engine(tmp_path, monkeypatch):
    commands = {
        name: EngineCommand(("fake", "-i", "{input}", "-o", "{output}"), timeout_seconds=900)
        for name in ENGINES
    }
    observed = {}

    def factory(value, *, execution_records=None):
        observed.update(value)
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination, *, engine=name):
                if execution_records is not None:
                    execution_records[engine] = {
                        "status": "output_ready",
                        "process_started": True,
                        "pid": 14000 + list(ENGINES).index(engine),
                        "exit_code": 0,
                        "process_elapsed_ms": 12,
                        "elapsed_ms_total": 15,
                    }
                with Image.open(source) as image:
                    image.resize(
                        (image.width * 2, image.height * 2),
                        Image.Resampling.LANCZOS,
                    ).save(destination, dpi=(300, 300),
                           icc_profile=image.info.get("icc_profile"))
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(qa, "load_real_engine_manifest", lambda *_: commands)
    monkeypatch.setattr(qa, "make_processors", factory)
    result = qa.run(
        tmp_path / "manifest.json", _source(tmp_path), tmp_path / "bounded",
        timeout_seconds=75,
    )
    assert result["real_inference_verified"] is True
    assert result["native_process_execution_verified"] is True
    assert all(command.timeout_seconds == 75 for command in observed.values())



def test_vulkan_initialization_failure_is_host_block_not_engine_quality_failure(
    tmp_path, monkeypatch
):
    calls = _prepare(
        monkeypatch,
        failed_engine="real_esrgan",
        failure_message="engine exited with code 4294967295: vkCreateInstance failed -9; invalid gpu device",
    )
    result = qa.run(
        tmp_path / "manifest.json",
        _source(tmp_path),
        tmp_path / "vulkan-blocked",
    )
    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is False
    failure = result["failures"]["real_esrgan"]
    assert failure["error_class"] == "vulkan_initialization_failed"
    assert failure["retry_on_vulkan_capable_host"] is True
    assert result["completed_engine_count"] == 3


def test_waifu2x_access_violation_is_not_masked_by_vulkan_stderr(tmp_path, monkeypatch):
    calls = _prepare(
        monkeypatch,
        failed_engine="waifu2x",
        failure_exit_code=0xC0000005,
        failure_message=(
            "engine exited with code 3221225477: "
            "vkCreateInstance failed -9"
        ),
    )
    result = qa.run(
        tmp_path / "manifest.json",
        _source(tmp_path),
        tmp_path / "waifu2x-access-violation",
    )

    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is False
    assert result["completed_engine_count"] == 3
    failure = result["failures"]["waifu2x"]
    assert failure["error_class"] == "windows_access_violation"
    assert failure["process"]["exit_code"] == 0xC0000005
    assert failure["process"]["exit_code_hex"] == "0xC0000005"
    assert failure["vulkan_error_observed"] is True
    assert "retry_on_vulkan_capable_host" not in failure


@pytest.mark.parametrize("exit_code", (0xC0000005, -1073741819))
def test_access_violation_ntstatus_is_normalized_before_vulkan_classification(exit_code):
    error_class, retryable = qa._classify_engine_failure(
        RuntimeError("engine exited with code: vkCreateInstance failed -9"),
        {"exit_code": exit_code},
    )
    assert error_class == "windows_access_violation"
    assert retryable is False


def test_non_vulkan_native_failure_remains_a_candidate_failure(tmp_path, monkeypatch):
    _prepare(
        monkeypatch,
        failed_engine="waifu2x",
        failure_message="engine exited with code 1: invalid model arguments",
    )
    result = qa.run(
        tmp_path / "manifest.json",
        _source(tmp_path),
        tmp_path / "native-failure",
    )
    assert result["failures"]["waifu2x"]["error_class"] == "subprocess_or_candidate_failure"
    assert "retry_on_vulkan_capable_host" not in result["failures"]["waifu2x"]

def test_invalid_gpu_device_index_is_not_misclassified_as_host_vulkan_absence():
    error_class, retryable = qa._classify_engine_failure(
        RuntimeError("engine exited with code 1: invalid gpu device")
    )
    assert error_class == "subprocess_or_candidate_failure"
    assert retryable is False


@pytest.mark.parametrize("mutation", ("invent_alpha", "invent_icc", "invent_dpi"))
def test_native_qa_rejects_engine_added_mode_or_metadata(tmp_path, monkeypatch, mutation):
    calls = []

    def factory(_manifest, *, execution_records=None):
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination, *, engine=name):
                calls.append(engine)
                with Image.open(source) as image:
                    output = image.resize(
                        (image.width * 2, image.height * 2),
                        Image.Resampling.LANCZOS,
                    )
                    options = {}
                    if mutation == "invent_alpha":
                        output = output.convert("RGBA")
                    elif mutation == "invent_icc":
                        options["icc_profile"] = b"unexpected-profile"
                    elif mutation == "invent_dpi":
                        options["dpi"] = (300, 300)
                    output.save(destination, **options)
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(
        qa, "load_real_engine_manifest", lambda *_: {"test": "fake manifest"}
    )
    monkeypatch.setattr(qa, "make_processors", factory)
    result = qa.run(
        tmp_path / "manifest.json",
        _source(tmp_path, dpi=False),
        tmp_path / ("metadata-" + mutation),
    )

    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is False
    assert result["completed_engine_count"] == 0
    assert set(result["failures"]) == set(ENGINES)
    assert all(item["error_type"] == "ValueError" for item in result["failures"].values())


def test_native_qa_accepts_absent_icc_and_dpi_when_output_also_absent(
    tmp_path, monkeypatch
):
    calls = []

    def factory(_manifest, *, execution_records=None):
        mapping = {}
        for name in ENGINES:
            def candidate(source, destination, *, engine=name):
                calls.append(engine)
                if execution_records is not None:
                    execution_records[engine] = {
                        "status": "output_ready",
                        "process_started": True,
                        "pid": 13000 + list(ENGINES).index(engine),
                        "exit_code": 0,
                        "process_elapsed_ms": 12,
                        "elapsed_ms_total": 15,
                    }
                with Image.open(source) as image:
                    image.resize(
                        (image.width * 2, image.height * 2),
                        Image.Resampling.LANCZOS,
                    ).save(destination)
            mapping[name] = candidate
        return mapping

    monkeypatch.setattr(
        qa, "load_real_engine_manifest", lambda *_: {"test": "fake manifest"}
    )
    monkeypatch.setattr(qa, "make_processors", factory)
    source = _source(tmp_path, dpi=False)
    result = qa.run(
        tmp_path / "manifest.json", source, tmp_path / "no-source-metadata"
    )

    assert calls == list(ENGINES)
    assert result["real_inference_verified"] is True
    assert result["candidate_output_validation_complete"] is True
    assert result["native_process_execution_verified"] is True
    assert result["completed_engine_count"] == 4
    assert not result["failures"]
    for engine in ENGINES:
        assert result["engines"][engine]["icc_preserved"] is True
        assert result["engines"][engine]["dpi_preserved"] is True
        with Image.open(tmp_path / "no-source-metadata" / f"{engine}.png") as output:
            assert output.info.get("icc_profile") is None
            assert output.info.get("dpi") is None

