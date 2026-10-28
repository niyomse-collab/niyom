"""Regression: V2.1 graphic toggle and face controls must not overlap."""
import ast
from pathlib import Path


def test_v21_optional_ai_checkbox_has_own_grid_row():
    source = (Path(__file__).resolve().parents[1] / "signprint_ai" / "app_v2.py").read_text(encoding="utf-8")
    root = ast.parse(source)
    app_class = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == "App")
    controls = next(n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == "_build_controls")
    grids = []
    for node in ast.walk(controls):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "grid":
            continue
        section = ast.get_source_segment(source, node) or ""
        row = next((kw.value.value for kw in node.keywords if kw.arg == "row" and isinstance(kw.value, ast.Constant)), None)
        if row is not None:
            grids.append((section, row))

    graphic_row = next(row for section, row in grids if "self.graphic_ai_var" in section)
    divider_row = next(row for section, row in grids if 'tk.Frame(quality, bg="#37414B", height=1)' in section)
    face_row = next(row for section, row in grids if "self.face_enabled_var" in section)
    mode_row = next(row for section, row in grids if "face_mode.grid" in section)
    assert (graphic_row, divider_row, face_row, mode_row) == (6, 7, 8, 9)
    strength_row = next(row for section, row in grids if '"Face Strength"' in section) if False else None
    assert "self.graphic_ai_var = tk.BooleanVar(value=False)" in source
