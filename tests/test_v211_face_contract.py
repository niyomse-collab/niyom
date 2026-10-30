"""V2.1.1 regression gates for user-approved V2 portrait baseline."""
from types import SimpleNamespace

import pytest

from signprint_ai.v211_face_contract import enforce_requested_face_restoration


def settings(**kw):
    base = dict(v211_require_face_restore=True, face_protection=True,
                face_mode="recover")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("reason", [None, "model missing", "face was not detected"])
def test_requested_recover_does_not_silently_export_when_skipped(reason):
    with pytest.raises(RuntimeError, match="ฟื้นฟูใบหน้าไม่สำเร็จ") as error:
        enforce_requested_face_restoration(
            settings(), {"applied": False, "face_count": 0,
                         "skipped_reason": reason})
    assert "V2.1.1" in str(error.value)


@pytest.mark.parametrize("mode", ["recover", "studio ai", "Recover"])
def test_restored_face_pass_accepts_only_real_nonzero_count(mode):
    enforce_requested_face_restoration(
        settings(face_mode=mode),
        {"applied": True, "face_count": 1, "skipped_reason": None})
    with pytest.raises(RuntimeError):
        enforce_requested_face_restoration(
            settings(face_mode=mode), {"applied": True, "face_count": 0})


def test_requested_face_recovery_cannot_be_noop_ai():
    with pytest.raises(RuntimeError, match="ไม่ได้เปิดการประมวลผล AI"):
        enforce_requested_face_restoration(settings(), None, use_ai=False)
    with pytest.raises(RuntimeError, match="ไม่ได้เปิดการประมวลผล AI"):
        enforce_requested_face_restoration(settings(), None, model_scale=1)


@pytest.mark.parametrize("flags", [
    {"face_protection": False},
    {"face_mode": "protect"},
    {"v211_require_face_restore": False},
])
def test_not_requested_or_legacy_paths_are_unchanged(flags):
    enforce_requested_face_restoration(settings(**flags), {"applied": False})


def test_v211_contract_wired_before_small_and_large_exports():
    import inspect
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.large_image import _large_job

    small = inspect.getsource(NiyomSilpCoreAdapter.process)
    large = inspect.getsource(_large_job)
    assert small.index("enforce_requested_face_restoration(") < small.index("dst.parent.mkdir(")
    assert large.index("enforce_requested_face_restoration(") < large.index("export_image(")


def test_v211_ui_label_and_old_v21_version_are_distinct(monkeypatch):
    from signprint_ai import v21_brand
    monkeypatch.setattr(v21_brand, "load_release_info",
                        lambda: {"channel": "v2", "version": "2.1.1-beta.7"})
    assert v21_brand.release_label() == "v2.1.1"
    monkeypatch.setattr(v21_brand, "load_release_info",
                        lambda: {"channel": "v2", "version": "2.1.0-beta.7"})
    assert v21_brand.release_label() == "v2.1"
