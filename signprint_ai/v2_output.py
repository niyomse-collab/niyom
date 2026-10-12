"""Safe V2 output naming, independent of the approved V1 application and files."""
from pathlib import Path


V2_OUTPUT_FOLDER = "NiyomSilpDesignV2_Outputs"


def output_folder(source, selected_directory):
    """Use a dedicated V2 result folder; never select the V1 application tree."""
    src = Path(source)
    folder = (Path(selected_directory) if selected_directory
              else src.parent / V2_OUTPUT_FOLDER)
    if any(part.casefold() == "niyomsilpdesignv1" for part in folder.parts):
        raise ValueError("ไม่อนุญาตให้บันทึกงาน V2 ลงในโฟลเดอร์ติดตั้ง V1")
    return folder


def output_path(source, selected_directory, export_format, color_mode, occupied=()):
    """Choose a V2-only destination without overwriting a pre-existing file.

    A user-selected output folder is still honored, but legacy V1 results are
    not overwritten: V2 filenames have a distinct tag and use numbered names
    if an output already exists.
    """
    src = Path(source)
    ext = {"PNG": ".png", "TIFF": ".tif", "PDF": ".pdf", "JPG": ".jpg"}[export_format]
    folder = output_folder(src, selected_directory)
    color_suffix = "_CMYK" if color_mode.upper() == "CMYK" else ""
    base = f"{src.stem}_NiyomSilp_V2_AI{color_suffix}"
    reserved = {str(Path(item)).casefold() for item in occupied}
    for index in range(1, 1_000_001):
        name = f"{base}{ext}" if index == 1 else f"{base}_{index}{ext}"
        candidate = folder / name
        if not candidate.exists() and str(candidate).casefold() not in reserved:
            return candidate
    raise RuntimeError("ไม่สามารถกำหนดชื่อไฟล์ผลลัพธ์ V2 ที่ไม่ซ้ำได้")
