"""V2.1.1 face-restoration execution contract (independent of V1/V2).

A requested Recover/Studio AI pass is not successful just because the
photo/garment upscaler finished. Fail *before exporting* if face restoration
was skipped. This does not assert that a restored face passed visual QA.
"""
from __future__ import annotations


RESTORATION_MODES = frozenset(("recover", "studio ai"))


def enforce_requested_face_restoration(settings, face_info, *, use_ai=True, model_scale=4):
    """Raise when the operator requested restoration but no face was restored.

    Leave Protect (source-face preservation) and jobs without a selected
    face untouched. The result dictionary is never mutated.
    """
    if not getattr(settings, "v211_require_face_restore", False):
        return
    if not getattr(settings, "face_protection", False):
        return
    if str(getattr(settings, "face_mode", "")).strip().lower() not in RESTORATION_MODES:
        return
    if not use_ai or model_scale <= 1:
        raise RuntimeError(
            "V2.1.1: ขอฟื้นฟูใบหน้าแต่ไม่ได้เปิดการประมวลผล AI "
            "กรุณาเปิด AI 2x/4x/8x หรือยกเลิกโหมดฟื้นฟูใบหน้า"
        )
    info = face_info or {}
    if info.get("applied") and int(info.get("face_count") or 0) > 0:
        return
    reason = str(info.get("skipped_reason") or "ตรวจไม่พบใบหน้าที่ฟื้นฟูสำเร็จ")
    raise RuntimeError(
        "V2.1.1: ฟื้นฟูใบหน้าไม่สำเร็จ จึงหยุดก่อนส่งออก "
        "เพื่อไม่ให้ได้ภาพเสื้อคมแต่ใบหน้าเบลอ — " + reason
    )
