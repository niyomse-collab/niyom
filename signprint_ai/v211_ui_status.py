"""Small, dependency-free UI messages for V2.1.1 auxiliary-engine gates."""
from __future__ import annotations


def four_engine_ui_status(status: object) -> dict[str, object] | None:
    """Describe fail-closed auxiliary AI states without implying V2 failed."""
    if str(status or "").strip() != "gpu_runtime_unverified":
        return None
    return {
        "row": "V2 สำเร็จ • AI 4 รอ GPU QA",
        "caption": (
            "AI 4 ตัว: ยังยืนยันการใช้ GPU บน GTX 1660 Ti ไม่ครบ "
            "• ไม่สร้างภาพ QA • ใช้ภาพ V2 เดิม"
        ),
        "allow_preview": False,
    }
