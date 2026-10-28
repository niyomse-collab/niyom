# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import importlib.metadata
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
    "pyvips",
    "_libvips",
]
# BasicSR discovers several modules dynamically (including basicsr.ops).
# Freeze the complete Python module graph so the packaged EXE does not fail
# at runtime with missing fused_act/upfirdn2d or another dynamically imported
# BasicSR module.
hiddenimports += collect_submodules("basicsr")
hiddenimports += collect_submodules("realesrgan")
hiddenimports += collect_submodules("gfpgan")
hiddenimports += collect_submodules("facexlib")

dynamic_files = []
for package, folders in {
    # Keep .py files visible on disk as well because BasicSR scans folders
    # at runtime to discover *_arch.py, *_dataset.py, *_loss.py, etc.
    "basicsr": ("archs", "data", "losses", "models", "ops", "utils"),
    "realesrgan": ("archs", "data", "models"),
    "gfpgan": ("archs", "data", "models", "utils"),
    "facexlib": ("alignment", "detection", "headpose", "parsing", "recognition", "tracking", "utils"),
}.items():
    package_spec = importlib.util.find_spec(package)
    if package_spec is None or not package_spec.origin:
        raise RuntimeError("Required package not found: " + package)
    package_root = Path(package_spec.origin).parent
    for folder_name in folders:
        folder = package_root / folder_name
        if folder.is_dir():
            dynamic_files.extend(
                (
                    str(path),
                    package + "/" + str(path.parent.relative_to(package_root)).replace("\\", "/"),
                )
                for path in sorted(folder.rglob("*.py"))
            )

datas = [
    (str(ROOT / "models"), "models"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "README_TH.md"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "NOTICE_INDEPENDENT_PROJECT.txt"), "."),
] + dynamic_files

if (ROOT / "build_info.json").is_file():
    datas.append((str(ROOT / "build_info.json"), "."))
if (ROOT / "README_V2_TH.md").is_file():
    datas.append((str(ROOT / "README_V2_TH.md"), "."))

# pyvips-binary is a binary distribution, not an importable Python package.
# Collect its native extension/DLLs and bundled license files explicitly.
vips_binaries = []
for distribution_name in ("pyvips-binary", "pyvips", "tifffile"):
    distribution = importlib.metadata.distribution(distribution_name)
    for item in distribution.files or []:
        path = Path(distribution.locate_file(item))
        destination = str(Path(str(item)).parent).replace("\\", "/")
        if path.suffix.lower() in (".dll", ".pyd", ".so") or ".so." in path.name:
            vips_binaries.append((str(path), destination))
        elif "licenses" in str(item).lower() or path.name.startswith(".load-order-"):
            datas.append((str(path), destination))

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=vips_binaries,
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
