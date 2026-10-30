"""UI contract: portrait modes live in the main panel, not face-selection popup."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_face_mode_menu_only_has_protect_recover_and_studio_ai():
    source = (ROOT / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'self.face_mode_var = tk.StringVar(value="Recover")' in source
    assert 'values=("Protect", "Recover", "Studio AI")' in source
    assert 'text="Recover: ฟื้นฟูใบหน้า (แนะนำ) • Protect: ใช้ใบหน้าต้นฉบับ ไม่ฟื้นฟู • Studio AI: ฟื้นฟูและแต่งผิว"' in source
    assert 'values=("Studio AI", "Studio", "Protect", "Recover")' not in source
    assert 'text="NiyomSilp Design • ปรับภาพบุคคล"' in source


def test_face_selection_popup_only_chooses_faces():
    source = (ROOT / "signprint_ai" / "face_module" / "selection.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert "NiyomSilp Design — เลือกใบหน้า" in source
    assert "def choose_faces(" in source
    assert "Combobox(" not in source
    assert "face_mode" not in source
    assert "ยืนยันใบหน้าที่เลือก" in source
