"""Bridge error summaries must never expose native stderr or customer paths."""
import logging

from PIL import Image

from signprint_ai import v211_four_engine_bridge as bridge
from tools import v211_four_engine_run


def test_native_exception_message_is_redacted_from_result_and_logs(
    tmp_path, monkeypatch, caplog
):
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-V2.png"
    Image.new("RGB", (8, 8), (25, 80, 120)).save(source)
    Image.new("RGB", (16, 16), (25, 80, 120)).save(baseline)
    original_v2 = baseline.read_bytes()
    private_path = str(tmp_path / "customer artwork" / "customer-name-phone.png")

    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST",
        str(tmp_path / "installed-manifest.json"),
    )
    monkeypatch.delenv("NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR", raising=False)

    def bind_manifest(_manifest, work_dir):
        bound = work_dir / "manifest.runtime-bound.json"
        bound.write_text("{}", encoding="utf-8")
        return bound, {"binding_configured": True, "runtime_device_use_verified": False}

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", bind_manifest)

    def fail_with_private_path(*args, **kwargs):
        raise RuntimeError("native engine failed while opening " + private_path)

    monkeypatch.setattr(v211_four_engine_run, "run", fail_with_private_path)
    caplog.set_level(logging.WARNING, logger=bridge.__name__)

    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert result["error_class"] == "processing_failed"
    assert result["v2_output_preserved"] is True
    assert private_path not in repr(result)
    assert private_path not in caplog.text
    assert baseline.read_bytes() == original_v2
    assert not list(tmp_path.glob("*.V211-4AI-QA-*.png"))


def test_gpu_binding_failure_uses_static_safe_reason(tmp_path, monkeypatch, caplog):
    source = tmp_path / "source.png"
    baseline = tmp_path / "accepted-V2.png"
    Image.new("RGB", (8, 8), (25, 80, 120)).save(source)
    Image.new("RGB", (16, 16), (25, 80, 120)).save(baseline)
    original_v2 = baseline.read_bytes()
    private_path = str(tmp_path / "customer-secret" / "private.png")

    monkeypatch.setenv("NIYOMSIL_V211_FOUR_AI", "1")
    monkeypatch.setenv(
        "NIYOMSIL_V211_FOUR_AI_MANIFEST",
        str(tmp_path / "installed-manifest.json"),
    )

    def fail_binding(_manifest, _work_dir):
        raise bridge.GPUDeviceBindingError("ambiguous device at " + private_path)

    monkeypatch.setattr(bridge, "_prepare_runtime_bound_manifest", fail_binding)
    caplog.set_level(logging.WARNING, logger=bridge.__name__)

    result = bridge.maybe_run_four_engine_assist(source, baseline)

    assert result["status"] == "gpu_binding_unverified"
    assert "ambiguous" in result["reason"]
    assert private_path not in repr(result)
    assert private_path not in caplog.text
    assert baseline.read_bytes() == original_v2
