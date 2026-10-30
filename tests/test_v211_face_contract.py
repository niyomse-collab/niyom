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

@pytest.mark.parametrize("mode", ["recover", "studio ai"])
def test_selected_multiple_faces_must_all_restore(mode):
    selected = ((0.05, 0.05, 0.40, 0.40), (0.55, 0.55, 0.95, 0.95))
    selected_settings = settings(face_mode=mode, face_regions=selected)
    with pytest.raises(RuntimeError, match="1/2"):
        enforce_requested_face_restoration(
            selected_settings, {"applied": True, "face_count": 1,
                                "skipped_reason": "second face failed"})
    enforce_requested_face_restoration(
        selected_settings, {"applied": True, "face_count": 2,
                            "skipped_reason": None})


def test_partial_face_skip_reason_is_never_ignored():
    selected = ((0.05, 0.05, 0.40, 0.40), (0.55, 0.55, 0.95, 0.95))
    with pytest.raises(RuntimeError, match="second face failed"):
        enforce_requested_face_restoration(
            settings(face_regions=selected),
            {"applied": True, "face_count": 2,
             "skipped_reason": "second face failed"})


def test_empty_explicit_face_selection_does_not_require_restoration():
    enforce_requested_face_restoration(
        settings(face_regions=()), None, use_ai=False)


def test_auto_detect_still_requires_one_successful_face():
    with pytest.raises(RuntimeError, match="ฟื้นฟูใบหน้าไม่สำเร็จ"):
        enforce_requested_face_restoration(
            settings(face_regions=None), {"applied": False, "face_count": 0})


@pytest.mark.parametrize("studio_completed", [0, 1, 2])
def test_studio_ai_reports_actual_completed_faces(monkeypatch, studio_completed):
    """Recover success must not mask a partially skipped Studio AI ROI."""
    from PIL import Image
    from signprint_ai.face_module import studio
    from signprint_ai.face_module.face_protection import (
        FaceProtectionModule, FaceProtectionResult,
    )

    regions = ((0.05, 0.05, 0.40, 0.40),
               (0.55, 0.55, 0.95, 0.95))
    original_apply = FaceProtectionModule.apply

    def recover_stub(self, image, **kwargs):
        if kwargs.get("mode") == "recover":
            return image, FaceProtectionResult(
                enabled=True, applied=True, face_count=2,
                mode="recover", strength=35,
            )
        return original_apply(self, image, **kwargs)

    def studio_stub(output, source_path, selected, strength, resize_mode,
                    cancel, progress, source_image=None):
        assert len(selected) == 2
        assert source_image is not None
        return output, studio_completed

    monkeypatch.setattr(FaceProtectionModule, "apply", recover_stub)
    monkeypatch.setattr(studio, "apply_studio", studio_stub)
    _, info = FaceProtectionModule().apply(
        Image.new("RGB", (32, 32)), device_name="cpu",
        mode="studio ai", strength=35, regions=regions,
    )
    assert info.face_count == studio_completed
    assert info.applied is (studio_completed > 0)
    if studio_completed < 2:
        assert f"{studio_completed}/2" in info.skipped_reason
        with pytest.raises(RuntimeError, match="หยุดก่อนส่งออก"):
            enforce_requested_face_restoration(
                settings(face_mode="studio ai", face_regions=regions),
                info.as_dict(),
            )
    else:
        assert info.skipped_reason is None
        enforce_requested_face_restoration(
            settings(face_mode="studio ai", face_regions=regions),
            info.as_dict(),
        )
