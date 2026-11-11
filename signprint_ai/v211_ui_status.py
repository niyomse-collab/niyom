"""Small, dependency-free UI messages for V2.1.1 auxiliary-engine gates."""
from __future__ import annotations


_PREVIEW_READY_STATUSES = frozenset({
    "four_engine_fusion_preview_ready",
    "three_engine_priority_preview_ready",
})


def _blocked_status(row: str, caption: str) -> dict[str, object]:
    return {"row": row, "caption": caption, "allow_preview": False}


def four_engine_ui_status(
    status: object, *, qa_file_exists: object | None = None
) -> dict[str, object] | None:
    """Describe auxiliary-AI states without marking an unverified result successful.

    qa_file_exists=None preserves the helper's standalone ready-state behavior.
    The application passes an explicit boolean so a ready status without its
    sidecar is surfaced as an incomplete QA result.
    """
    value = str(status or "").strip()

    if value in _PREVIEW_READY_STATUSES:
        if qa_file_exists is False:
            return _blocked_status(
                "V2 สำเร็จ • AI 4 ไม่พบไฟล์ QA",
                "AI 4: สถานะพร้อมแต่ไม่พบไฟล์ QA • ไม่แสดงภาพตัวอย่าง • ใช้ภาพ V2 เดิม",
            )
        return None

    if not value:
        if qa_file_exists is None:
            return None
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ไม่มีสถานะ QA",
            "AI 4: ไม่มีสถานะยืนยันผล QA • ไม่แสดงภาพตัวอย่าง • ใช้ภาพ V2 เดิม",
        )

    if value == "gpu_runtime_unverified":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 รอ GPU QA",
            (
                "AI 4 ตัว: ยังยืนยันการใช้ GPU บน GTX 1660 Ti ไม่ครบ "
                "• ไม่สร้างภาพ QA • ใช้ภาพ V2 เดิม"
            ),
        )

    if value == "gpu_binding_unverified":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 รอยืนยัน GPU",
            (
                "AI 4 ตัว: ระบุการ์ดจอ GTX 1660 Ti ได้ไม่ชัดเจน "
                "• ไม่แสดงภาพ QA • ใช้ภาพ V2 เดิม"
            ),
        )

    if value == "four_engine_fusion_contribution_incomplete":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 QA ไม่ครบ",
            (
                "AI 4 ตัว: มี Engine อย่างน้อยหนึ่งตัวไม่เปลี่ยนพิกเซลผลลัพธ์ "
                "• ไม่แสดงภาพ QA • ใช้ภาพ V2 เดิม"
            ),
        )

    if value == "models_not_installed":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ยังไม่ติดตั้ง",
            "AI 4 ตัว: ยังไม่มีโมเดลที่ตรวจสอบและติดตั้งครบ • ใช้ภาพ V2 เดิม",
        )

    if value == "disabled":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ปิดอยู่",
            "ปิดการใช้ AI เสริม • ใช้ภาพ V2 เดิม",
        )

    if value == "cancelled":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ยกเลิกแล้ว",
            "AI 4 ตัว: ยกเลิกการประมวลผล • ภาพ V2 เดิมยังอยู่",
        )

    if value == "face_protection_v2_only":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ข้ามเพื่อปกป้องใบหน้า",
            (
                "AI 4 ตัว: ไม่พบขอบเขตใบหน้าที่จับคู่ได้อย่างปลอดภัย "
                "• ใช้ภาพ V2 เดิม"
            ),
        )

    if value == "large_image_tiling_pending":
        return _blocked_status(
            "V2 สำเร็จ • AI 4 รอรองรับงานใหญ่",
            "AI 4 ตัว: งานภาพขนาดใหญ่นี้ยังไม่พร้อม • ใช้ภาพ V2 เดิม",
        )

    if value in {
        "auxiliary_image_too_large",
        "auxiliary_engine_scale_mismatch",
        "unsupported_output_format",
        "unsupported_source_format",
        "unsupported_source_mode",
        "unsupported_colour_mode",
        "unsupported_target_geometry",
    }:
        return _blocked_status(
            "V2 สำเร็จ • AI 4 ไม่รองรับรูปแบบนี้",
            "AI 4 ตัว: ขนาด สเกล หรือรูปแบบไฟล์ยังไม่รองรับ • ใช้ภาพ V2 เดิม",
        )

    if value in {
        "error",
        "incomplete_four_engine_candidates",
        "candidate_research_complete",
        "four_engine_error",
        "four_engine_incomplete",
        "four_engine_no_pixel_effect",
        "processing_failed",
        "setup_failed",
        "four_ai_setup_failed",
    }:
        return _blocked_status(
            "V2 สำเร็จ • AI 4 QA ไม่ครบ",
            "AI 4 ตัว: ยังไม่ผ่านเงื่อนไข QA ครบทั้งสี่ • ไม่แสดงภาพ QA • ใช้ภาพ V2 เดิม",
        )

    # Unknown non-empty statuses must never fall through to the app's generic
    # success row. This protects the UI when a future bridge status is added
    # before its Thai explanation and acceptance behavior are reviewed.
    return _blocked_status(
        "V2 สำเร็จ • AI 4 รอตรวจสอบ",
        "AI 4 ตัว: สถานะนี้ยังไม่อยู่ในรายการที่อนุญาตให้แสดง QA • ใช้ภาพ V2 เดิม",
    )


def four_engine_preview_allowed(qa_file_exists: object, status: object) -> bool:
    """Allow a sidecar preview only for an explicitly recognized ready state."""
    if not bool(qa_file_exists):
        return False
    value = str(status or "").strip()
    return value in _PREVIEW_READY_STATUSES



def four_engine_preview_caption(status: object) -> str:
    """Name the actual engine set represented by a QA preview."""
    value = str(status or "").strip()
    if value == "three_engine_priority_preview_ready":
        return (
            "QA สำรองจาก Real-ESRGAN, Waifu2x และ Real-CUGAN เท่านั้น "
            "• Anime4K ไม่ได้ร่วมในภาพนี้ • ไฟล์ V2 เดิมยังอยู่ "
            "• ไม่ใช่ผลรับรองคุณภาพ"
        )
    if value == "four_engine_fusion_preview_ready":
        return (
            "QA จาก AI ทั้ง 4 ตัวมีส่วนต่อพิกเซลแล้ว "
            "• ไฟล์ V2 เดิมยังอยู่ • ไม่ใช่ผลรับรองคุณภาพ"
        )
    return "ภาพ QA จาก AI เสริม • ไฟล์ V2 เดิมยังอยู่ • ไม่ใช่ผลรับรองคุณภาพ"
