"""Small, dependency-free UI messages for V2.1.1 auxiliary-engine gates."""
from __future__ import annotations


_PREVIEW_READY_STATUSES = frozenset({
    "four_engine_fusion_preview_ready",
    "three_engine_priority_preview_ready",
})


def four_engine_ui_status(status: object) -> dict[str, object] | None:
    """Describe fail-closed auxiliary AI states without implying V2 failed."""
    value = str(status or "").strip()
    if value == "gpu_runtime_unverified":
        return {
            "row": "V2 สำเร็จ • AI 4 รอ GPU QA",
            "caption": (
                "AI 4 ตัว: ยังยืนยันการใช้ GPU บน GTX 1660 Ti ไม่ครบ "
                "• ไม่สร้างภาพ QA • ใช้ภาพ V2 เดิม"
            ),
            "allow_preview": False,
        }
    if value == "four_engine_fusion_contribution_incomplete":
        return {
            "row": "V2 สำเร็จ • AI 4 QA ไม่ครบ",
            "caption": (
                "AI 4 ตัว: มี Engine อย่างน้อยหนึ่งตัวไม่เปลี่ยนพิกเซลผลลัพธ์ "
                "• ไม่แสดงภาพ QA • ใช้ภาพ V2 เดิม"
            ),
            "allow_preview": False,
        }
    return None


def four_engine_preview_allowed(qa_file_exists: object, status: object) -> bool:
    """Allow a sidecar preview only for an explicitly recognized ready state."""
    if not bool(qa_file_exists):
        return False
    value = str(status or "").strip()
    return value in _PREVIEW_READY_STATUSES
