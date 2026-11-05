# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import importlib.metadata
from pathlib import Path
import sys
import types

# PyInstaller analyses collect_submodules before runtime_hooks execute. BasicSR
# 1.4.2 still imports TorchVision's removed functional_tensor path, so install
# the same narrow rgb_to_grayscale compatibility alias in the analysis process.
try:
    from torchvision.transforms.functional import rgb_to_grayscale
except Exception as exc:
    raise RuntimeError(
        "TorchVision compatibility import required for BasicSR packaging"
    ) from exc

_compat_name = "torchvision.transforms.functional_tensor"
if _compat_name not in sys.modules:
    _compat_module = types.ModuleType(_compat_name)
    _compat_module.rgb_to_grayscale = rgb_to_grayscale
    sys.modules[_compat_name] = _compat_module

ROOT = Path(SPECPATH).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.v211_frozen_imports import discover_package_modules

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
    # Included for the explicit V2.1.1 research opt-in; not activated by default.
    "signprint_ai.v211_four_engine_bridge",
    "signprint_ai.v211_background_fusion",
    "tools.v211_four_engine_run",
    "tools.v211_four_engine_coordinator",
    "tools.v211_four_engine_subprocess",
    "tools.v211_real_engine_manifest",
    "tools.v211_four_engine_safe_selection",
    "tools.v211_three_engine_priority_preview",
    "tools.v211_four_engine_fusion",
    "signprint_ai.v211_auto_setup",
    "signprint_ai.v211_setup_cli",
    "tools.v211_official_assets_audit",
    "tools.v211_provision_four_engines",
    "tools.v211_shop_gpu_diagnostic",
]
# BasicSR discovers several modules dynamically (including basicsr.ops).
# Do not use collect_submodules here: PyInstaller executes that helper in an
# isolated interpreter, which does not inherit the analysis-process alias above.
# Static filesystem discovery preserves the full module graph without importing
# BasicSR during collection; the runtime hook supplies the legacy import alias.
for package in ("basicsr", "realesrgan", "gfpgan", "facexlib"):
    package_spec = importlib.util.find_spec(package)
    if package_spec is None or not package_spec.origin:
        raise RuntimeError("Required package not found: " + package)
    hiddenimports += discover_package_modules(Path(package_spec.origin).parent, package)
hiddenimports = sorted(set(hiddenimports))

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
