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
    # A manually empty selection is not a requested face-restoration job.
    # Auto-detection (None) still requires at least one successful face.
    selected = getattr(settings, "face_regions", None)
    if selected is not None and len(selected) == 0:
        return
    required_count = len(selected) if selected is not None else 1
    if not use_ai or model_scale <= 1:
        raise RuntimeError(
            "V2.1.1: ขอฟื้นฟูใบหน้าแต่ไม่ได้เปิดการประมวลผล AI "
            "กรุณาเปิด AI 2x/4x/8x หรือยกเลิกโหมดฟื้นฟูใบหน้า"
        )
    info = face_info or {}
    restored_count = int(info.get("face_count") or 0)
    reason = str(info.get("skipped_reason") or "ตรวจไม่พบใบหน้าที่ฟื้นฟูสำเร็จ")
    # One restored face is NOT sufficient when the user selected two or more.
    # Disk-tile restoration may partially succeed while recording a skip reason.
    if (info.get("applied") and restored_count >= required_count
            and not info.get("skipped_reason")):
        # GFPGAN inference can finish and still produce an obvious bad face:
        # washed-out eyes, erased mouth or major colour drift. V2.1.1 is
        # fail-closed on *audited failures*, never silently substitutes an
        # unretouched blurry face or saves the bad crop. The accepted V2
        # processor itself is unchanged.
        if getattr(settings, "v211_reject_failed_face_audit", False):
            audits = info.get("face_audit") or ()
            for audit in audits:
                if audit.get("heuristic_pass") is False:
                    index = audit.get("index", "?")
                    reason = str(audit.get("reason") or "quality_audit_failed")
                    raise RuntimeError(
                        f"V2.1.1: ฟื้นฟูใบหน้าที่ {index} แล้วแต่ตรวจคุณภาพไม่ผ่าน "
                        f"({reason}) จึงหยุดก่อนส่งออก กรุณาตรวจใบหน้า "
                        "ปรับ Face Strength แล้วประมวลผลใหม่"
                    )
            # Explicit audited results must cover every successfully applied
            # face; no quiet omission of a failed/unaudited selected face.
            if audits and len(audits) < required_count:
                raise RuntimeError(
                    "V2.1.1: รายงานตรวจคุณภาพใบหน้าไม่ครบจำนวนที่เลือก "
                    "หยุดก่อนส่งออกเพื่อป้องกันใบหน้าเพี้ยน"
                )
        return
    if 0 < restored_count < required_count:
        reason = f"ฟื้นฟูได้เพียง {restored_count}/{required_count} ใบหน้า; {reason}"
    raise RuntimeError(
        "V2.1.1: ฟื้นฟูใบหน้าไม่สำเร็จ จึงหยุดก่อนส่งออก "
        "เพื่อไม่ให้ได้ภาพเสื้อคมแต่ใบหน้าเบลอ — " + reason
    )
