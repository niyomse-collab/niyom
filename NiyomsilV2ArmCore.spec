# -*- mode: python ; coding: utf-8 -*-
import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve()

hiddenimports = [
    "_tkinter",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.font",
    "tkinter.messagebox",
    "tkinter.ttk",
    "basicsr.archs.rrdbnet_arch",
    "basicsr.utils.flow_util",
    "realesrgan.archs.srvgg_arch",
]
hiddenimports += collect_submodules("basicsr.archs")
hiddenimports += collect_submodules("basicsr.losses")
hiddenimports += collect_submodules("basicsr.models")
hiddenimports += collect_submodules("realesrgan.archs")
hiddenimports += collect_submodules("realesrgan.data")
hiddenimports += collect_submodules("realesrgan.models")

dynamic_files = []
for package, folders in {
    "basicsr": ("archs", "data", "losses", "models"),
    "realesrgan": ("archs", "data", "models"),
}.items():
    package_spec = importlib.util.find_spec(package)
    if package_spec is None or not package_spec.origin:
        raise RuntimeError("Required package not found: " + package)
    package_root = Path(package_spec.origin).parent
    for folder_name in folders:
        folder = package_root / folder_name
        if folder.is_dir():
            dynamic_files.extend(
                (str(path), package + "/" + folder_name)
                for path in sorted(folder.glob("*.py"))
            )

datas = [
    (str(ROOT / "models"), "models"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "README_TH.md"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "NOTICE_INDEPENDENT_PROJECT.txt"), "."),
] + dynamic_files

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "pyi_rth_basicsr_compat.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NiyomsilAIEnhancer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NiyomsilAIEnhancer",
)
