"""Safe V2 output naming, independent of the approved V1 application and files."""
import os
from pathlib import Path


V2_OUTPUT_FOLDER = "NiyomSilpDesignV2_Outputs"
V1_UNINSTALL_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{D657F42C-17C9-43C9-88EA-41FCD2788931}_is1"
)


def _v1_install_locations():
    """Read the V1 install path, without opening or modifying V1 files."""
    if os.name != "nt":
        return ()
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, V1_UNINSTALL_KEY, 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            for name in ("InstallLocation", "Inno Setup: App Path"):
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                    if isinstance(value, str) and value.strip():
                        return (Path(value),)
                except FileNotFoundError:
                    continue
    except (OSError, ImportError):
        pass
    return ()


def _inside(directory, root):
    """Compare canonical paths; don't be fooled by subfolders or '..'."""
    try:
        destination = os.path.normcase(os.path.realpath(os.fspath(directory)))
        protected = os.path.normcase(os.path.realpath(os.fspath(root)))
        return os.path.commonpath((destination, protected)) == protected
    except (ValueError, OSError):
        return False


def output_folder(source, selected_directory):
    """Use a dedicated V2 result folder and avoid the entire installed V1 tree."""
    src = Path(source)
    folder = (Path(selected_directory) if selected_directory
              else src.parent / V2_OUTPUT_FOLDER)
    # Default V1 directory protection still applies if the registry is unavailable.
    if any(part.casefold() == "niyomsilpdesignv1" for part in folder.parts):
        raise ValueError("ไม่อนุญาตให้บันทึกงาน V2 ลงในโฟลเดอร์ติดตั้ง V1")
    for installed in _v1_install_locations():
        if _inside(folder, installed):
            raise ValueError("V2 cannot write into the registered V1 installation folder")
    return folder


def output_path(source, selected_directory, export_format, color_mode, occupied=()):
    """Choose a V2-only destination without overwriting existing or queued files.

    A user-selected output folder is honored. Legacy V1 outputs are protected
    by a distinct tag, and numbered V2 names avoid existing files.
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
