# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import importlib.metadata
import json
import re
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
build_info_path = ROOT / "build_info.json"
try:
    build_info = json.loads(build_info_path.read_text(encoding="utf-8-sig")) if build_info_path.is_file() else {}
except (OSError, ValueError, TypeError):
    build_info = {}

# Keep the V2.1.1 research graph isolated from the legacy V1 and stable-V2
# package graph. build_windows.ps1 writes build_info.json before PyInstaller.
IS_V211_BUILD = (
    isinstance(build_info, dict)
    and build_info.get("channel") == "v2"
    and re.fullmatch(
        r"2\.1\.1(?:-beta\.\d+)?",
        str(build_info.get("version") or ""),
    ) is not None
)

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

if IS_V211_BUILD:
    import sys
    import types

    # PyInstaller runs this spec in its analysis process; packaged runtime hooks
    # execute later and cannot repair imports needed during analysis. BasicSR
    # 1.4.2 still imports TorchVision's removed functional_tensor path.
    try:
        from torchvision.transforms.functional import rgb_to_grayscale
    except Exception as exc:
        raise RuntimeError(
            "TorchVision compatibility import required for V2.1.1 packaging"
        ) from exc

    _compat_name = "torchvision.transforms.functional_tensor"
    if _compat_name not in sys.modules:
        _compat_module = types.ModuleType(_compat_name)
        _compat_module.rgb_to_grayscale = rgb_to_grayscale
        sys.modules[_compat_name] = _compat_module

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.v211_frozen_imports import discover_package_modules

    hiddenimports += [
        "signprint_ai.v211_four_engine_bridge",
        "signprint_ai.v211_large_image_bridge",
        "signprint_ai.v211_background_fusion",
        "tools.v211_four_engine_run",
        "tools.v211_four_engine_coordinator",
        "tools.v211_four_engine_subprocess",
        "tools.v211_real_engine_manifest",
        "tools.v211_four_engine_safe_selection",
        "tools.v211_three_engine_priority_preview",
        "tools.v211_four_engine_fusion",
        "tools.v211_four_engine_tiled_inference",
        "signprint_ai.v211_auto_setup",
        "signprint_ai.v211_setup_cli",
        "tools.v211_official_assets_audit",
        "tools.v211_provision_four_engines",
        "tools.v211_shop_gpu_diagnostic",
        "signprint_ai.v211_cuda_compat",
        "tools.v211_gpu_device_binding",
        "tools.v211_gpu_process_telemetry",
    ]
    # Static filesystem discovery avoids collect_submodules' isolated import
    # interpreter, which does not inherit the analysis-process compatibility alias.
    for package in ("basicsr", "realesrgan", "gfpgan", "facexlib"):
        package_spec = importlib.util.find_spec(package)
        if package_spec is None or not package_spec.origin:
            raise RuntimeError("Required package not found: " + package)
        hiddenimports += discover_package_modules(Path(package_spec.origin).parent, package)
    hiddenimports = sorted(set(hiddenimports))
else:
    # Preserve the original V1 and stable-V2 PyInstaller module-discovery path.
    from PyInstaller.utils.hooks import collect_submodules

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
