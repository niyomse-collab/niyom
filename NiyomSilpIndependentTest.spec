# -*- mode: python ; coding: utf-8 -*-
"""Standalone TEST: original NiyomSilp GUI and independent experimental core."""
import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve()
hiddenimports = [
    "_tkinter", "tkinter", "tkinter.filedialog", "tkinter.font",
    "tkinter.messagebox", "tkinter.ttk",
    "basicsr.archs.rrdbnet_arch", "basicsr.utils.flow_util",
    "realesrgan.archs.srvgg_arch",
]
for package in ("basicsr", "realesrgan", "gfpgan", "facexlib"):
    hiddenimports += collect_submodules(package)

dynamic_files = []
for package, folders in {
    "basicsr": ("archs", "data", "losses", "models", "ops", "utils"),
    "realesrgan": ("archs", "data", "models"),
    "gfpgan": ("archs", "data", "models", "utils"),
    "facexlib": ("alignment", "detection", "headpose", "parsing",
                "recognition", "tracking", "utils"),
}.items():
    package_spec = importlib.util.find_spec(package)
    if package_spec is None or not package_spec.origin:
        raise RuntimeError("Required package missing: " + package)
    base = Path(package_spec.origin).parent
    for folder in folders:
        directory = base / folder
        if directory.is_dir():
            dynamic_files.extend(
                (str(file),
                 package + "/" + str(file.parent.relative_to(base)).replace("\\", "/"))
                for file in sorted(directory.rglob("*.py"))
            )

datas = [
    (str(ROOT / "models"), "models"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "NOTICE_INDEPENDENT_PROJECT.txt"), "."),
    (str(ROOT / "independent_core" / "README.md"), "."),
] + dynamic_files

a = Analysis(
    [str(ROOT / "run_independent_test.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "pyi_rth_basicsr_compat.py")],
    excludes=["app.device", "app.engine", "signprint_ai.arm_core_adapter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="NiyomSilpCoreTEST",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None, codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.ico"),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[], name="NiyomSilpCoreTEST",
)
