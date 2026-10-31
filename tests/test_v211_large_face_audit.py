"""Large vinyl confirmed-face GFPGAN audit must block bad output before save."""
from types import SimpleNamespace

import pytest

from signprint_ai.large_faces import append_selected_face_audit
from signprint_ai.v211_face_contract import enforce_requested_face_restoration


def _settings(regions):
    return SimpleNamespace(
        v211_require_face_restore=True,
        v211_reject_failed_face_audit=True,
        face_protection=True,
        face_mode="recover",
        face_regions=regions,
    )


def test_per_crop_gfpgan_audits_are_mapped_to_confirmed_large_image_face_selection():
    chosen=((.1,.1,.4,.4),(.52,.45,.91,.89))
    info={"applied": True, "face_count":2, "skipped_reason": None}
    good=SimpleNamespace(face_audit=(
        {"index":1,"model":"GFPGANv1.4","heuristic_pass":True,"reason":"accepted"},
    ))
    bad=SimpleNamespace(face_audit=(
        {"index":1,"model":"GFPGANv1.4","heuristic_pass":False,
         "reason":"local_face_detail_collapsed"},
    ))
    append_selected_face_audit(info,good,0)
    append_selected_face_audit(info,bad,1)
    assert [item["index"] for item in info["face_audit"]] == [1,2]
    assert [item["source"] for item in info["face_audit"]] == [
        "large_selected_face_roi","large_selected_face_roi"
    ]
    with pytest.raises(RuntimeError,match="ใบหน้าที่ 2"):
        enforce_requested_face_restoration(_settings(chosen),info)


def test_valid_large_crop_audits_allow_restoration_but_are_not_identity_proof():
    regions=((.1,.2,.8,.9),)
    info={"applied": True, "face_count":1, "skipped_reason": None}
    good=SimpleNamespace(face_audit=(
        {"index":1,"model":"GFPGANv1.4","heuristic_pass":True,
         "reason":"accepted"},
    ))
    append_selected_face_audit(info,good,0)
    enforce_requested_face_restoration(_settings(regions),info)
    assert info["face_audit"][0]["heuristic_pass"] is True


def test_partial_large_face_audit_and_selection_cannot_silently_pass():
    selected=((.02,.12,.42,.58),(.58,.11,.96,.61))
    info={"applied": True, "face_count":2, "skipped_reason": None}
    face=SimpleNamespace(face_audit=({"index":1,"heuristic_pass":True},))
    append_selected_face_audit(info,face,0)
    with pytest.raises(RuntimeError,match="ตรวจคุณภาพใบหน้าไม่ครบ"):
        enforce_requested_face_restoration(_settings(selected),info)


def test_missing_gfpgan_audit_does_not_count_as_audited_face():
    info={}
    append_selected_face_audit(info,SimpleNamespace(face_audit=()),0)
    assert info.get("face_audit",[]) == []
