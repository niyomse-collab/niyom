from signprint_ai.v211_ui_status import four_engine_ui_status


def test_gpu_runtime_unverified_has_explicit_v2_safe_thai_status():
    status = four_engine_ui_status("gpu_runtime_unverified")

    assert status is not None
    assert status["allow_preview"] is False
    assert "V2 สำเร็จ" in status["row"]
    assert "AI 4" in status["row"]
    assert "GTX 1660 Ti" in status["caption"]
    assert "ไม่สร้างภาพ QA" in status["caption"]
    assert "ใช้ภาพ V2 เดิม" in status["caption"]


def test_incomplete_four_engine_contribution_withholds_qa_preview():
    status = four_engine_ui_status("four_engine_fusion_contribution_incomplete")

    assert status is not None
    assert status["allow_preview"] is False
    assert "V2 สำเร็จ" in status["row"]
    assert "AI 4 QA ไม่ครบ" in status["row"]
    assert "Engine อย่างน้อยหนึ่งตัว" in status["caption"]
    assert "ไม่แสดงภาพ QA" in status["caption"]
    assert "ใช้ภาพ V2 เดิม" in status["caption"]


def test_other_four_engine_states_keep_existing_ui_handling():
    assert four_engine_ui_status("four_engine_fusion_preview_ready") is None
    assert four_engine_ui_status("models_not_installed") is None
    assert four_engine_ui_status(None) is None
