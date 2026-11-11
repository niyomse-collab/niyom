"""Preflight four official engine executables and model assets.

The manifest is not trusted merely because it contains self-reported hashes.
Every entry must match the repository's pinned upstream release provenance,
the expected executable/CLI contract, and one isolated engine directory.
No simulated inference or implicit downloads are performed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from tools.v211_four_engine_subprocess import ENGINES, EngineCommand
from tools import v211_official_assets_audit


EXECUTABLES = {
    "real_esrgan": "realesrgan-ncnn-vulkan.exe",
    "waifu2x": "waifu2x-ncnn-vulkan.exe",
    "real_cugan": "realcugan-ncnn-vulkan.exe",
    "anime4k": "ac_cli.exe",
}
MODEL_DIRECTORIES = {
    "real_esrgan": "models",
    "waifu2x": "models-cunet",
    "real_cugan": "models-se",
}
MODEL_NAMES = {
    "real_esrgan": "realesrgan-x4plus",
    "waifu2x": "2",
    "real_cugan": "1",
}
MODEL_SUFFIXES = {".param", ".bin", ".onnx", ".pth", ".safetensors", ".weights"}


def _verify_hash(path: Path, expected: str, engine: str) -> None:
    if (not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in expected)):
        raise ValueError(engine + ": expected_sha256 must be a 64-character hex digest")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.lower():
        raise ValueError(engine + ": SHA256 mismatch for " + str(path))


def _inside(path: Path, root: Path, engine: str, label: str) -> Path:
    """Resolve a regular path and reject symlinks or paths outside one engine root."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError(engine + ": " + label + " must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved_root = Path(root).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise ValueError(engine + ": " + label + " is outside its isolated engine directory") from exc
    return resolved


def _expected_provenance(engine: str) -> dict:
    package = v211_official_assets_audit.PACKAGES[engine]
    return {
        "source_url": package["url"],
        "license_name": package["license"],
        "license_url": package["license_url"],
        "additional_license_notices": package.get("additional_license_notices", []),
    }


def _expected_archive_digest(engine: str) -> tuple[str, str]:
    package = v211_official_assets_audit.PACKAGES[engine]
    published = package.get("release_sha256")
    observed = package.get("observed_sha256")
    digest = published or observed
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(engine + ": repository-pinned archive SHA256 is unavailable")
    source = "published_release_sha256" if published else "observed_ci_sha256"
    return digest, source


def _validate_args(engine: str, args: list, engine_root: Path) -> list[str]:
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError(engine + ": args must be a string array")

    # The installed manifest has no device flags. A per-run copy may add only
    # the explicit GPU selector produced by v211_gpu_device_binding. Validate
    # those flags here, then compare the remaining arguments exactly.
    base_args = list(args)
    if engine in ("real_esrgan", "waifu2x", "real_cugan"):
        positions = [
            index for index, token in enumerate(base_args)
            if token in ("-g", "--gpu")
        ]
        if len(positions) > 1:
            raise ValueError(engine + ": duplicate Vulkan GPU index")
        if positions:
            index = positions[0]
            if index + 1 >= len(base_args):
                raise ValueError(engine + ": Vulkan GPU index is missing")
            raw_index = base_args[index + 1]
            if not raw_index.isdecimal():
                raise ValueError(engine + ": Vulkan GPU index must be a non-negative integer")
            del base_args[index:index + 2]
    elif engine == "anime4k":
        processor_positions = [
            index for index, token in enumerate(base_args)
            if token in ("-p", "--processor")
        ]
        device_positions = [
            index for index, token in enumerate(base_args)
            if token in ("-d", "--device")
        ]
        if len(processor_positions) > 1 or len(device_positions) > 1:
            raise ValueError(engine + ": duplicate processor/device selection")
        if bool(processor_positions) != bool(device_positions):
            raise ValueError(engine + ": Anime4K processor and device must be selected together")
        if processor_positions:
            processor_index = processor_positions[0]
            device_index = device_positions[0]
            if processor_index + 1 >= len(base_args) or device_index + 1 >= len(base_args):
                raise ValueError(engine + ": Anime4K processor/device value is missing")
            if base_args[processor_index + 1] not in ("cuda", "opencl"):
                raise ValueError(engine + ": Anime4K processor must be CUDA or OpenCL")
            if not base_args[device_index + 1].isdecimal():
                raise ValueError(engine + ": Anime4K device index must be a non-negative integer")
            for index in sorted((processor_index, device_index), reverse=True):
                del base_args[index:index + 2]

    prefix = ["-i", "{input}", "-o", "{output}"]
    if engine == "anime4k":
        expected = prefix + ["-f", "2"]
        if base_args != expected:
            raise ValueError(engine + ": CLI arguments differ from the pinned v3.2.0 contract")
        return args

    if len(base_args) != 12 or base_args[:4] != prefix or base_args[4] != "-m":
        raise ValueError(engine + ": CLI arguments differ from the pinned NCNN contract")
    model_dir = Path(base_args[5])
    if not model_dir.is_absolute():
        raise ValueError(engine + ": model directory must be an absolute path")
    model_dir = _inside(model_dir, engine_root, engine, "model directory")
    if model_dir.name.casefold() != MODEL_DIRECTORIES[engine].casefold():
        raise ValueError(engine + ": unexpected NCNN model directory")
    if not model_dir.is_dir():
        raise ValueError(engine + ": NCNN model directory is missing")
    if not any(item.is_file() and item.suffix.lower() == ".param" for item in model_dir.iterdir()):
        raise ValueError(engine + ": NCNN model directory lacks a .param file")
    if not any(item.is_file() and item.suffix.lower() == ".bin" for item in model_dir.iterdir()):
        raise ValueError(engine + ": NCNN model directory lacks a .bin file")
    expected = prefix + [
        "-m", str(model_dir),
        "-n", MODEL_NAMES[engine],
        "-s", "2",
        "-t", "128",
    ]
    if base_args != expected:
        raise ValueError(engine + ": CLI arguments differ from the pinned NCNN model/scale contract")
    return args


def safe_manifest_path(path: Path) -> Path:
    """Return an absolute manifest path without following symlinks/reparse points.

    Inspect every existing component with lstat before any read, create or
    replace operation. This prevents a manifest symlink (or linked parent)
    from redirecting provisioning outside the intended user-local cache.
    """
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    for entry in (candidate, *candidate.parents):
        if entry == Path(candidate.anchor):
            continue
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError("manifest path cannot be safely inspected") from exc
        is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        if stat.S_ISLNK(info.st_mode) or is_reparse:
            raise ValueError("manifest path must not traverse a symlink or reparse point")
        if entry == candidate and not stat.S_ISREG(info.st_mode):
            raise ValueError("manifest must be a regular file")
    return candidate


def load_real_engine_manifest(path: Path) -> dict[str, EngineCommand]:
    manifest_path = safe_manifest_path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != set(ENGINES):
        raise ValueError("manifest must configure exactly four engines")

    commands = {}
    engine_roots = []
    for engine in ENGINES:
        item = data[engine]
        if not isinstance(item, dict):
            raise ValueError(engine + ": expected engine configuration")

        executable = Path(item.get("executable", ""))
        if not executable.is_absolute() or executable.is_symlink() or not executable.is_file():
            raise FileNotFoundError(engine + ": executable not installed")
        if executable.name.casefold() != EXECUTABLES[engine].casefold():
            raise ValueError(engine + ": unexpected official executable name")

        resolved_executable = executable.resolve(strict=True)
        engine_root = next(
            (parent for parent in resolved_executable.parents
             if parent.name.casefold() == engine.casefold()),
            None,
        )
        if engine_root is None or not engine_root.is_dir():
            raise ValueError(engine + ": executable is not inside its isolated engine directory")
        engine_root = engine_root.resolve(strict=True)
        executable = _inside(resolved_executable, engine_root, engine, "executable")
        engine_roots.append(engine_root)

        expected_archive, expected_digest_source = _expected_archive_digest(engine)
        if item.get("archive_sha256") != expected_archive:
            raise ValueError(engine + ": archive SHA256 does not match the repository-pinned release")
        # Older experimental manifests stored the pinned archive digest but
        # predated the explicit source label. Accept that legacy shape only
        # when the digest itself still matches the current repository pin.
        digest_source = item.get("archive_digest_source", expected_digest_source)
        if digest_source != expected_digest_source:
            raise ValueError(engine + ": archive digest source does not match the repository pin")

        provenance = item.get("provenance")
        if provenance != _expected_provenance(engine):
            raise ValueError(engine + ": source/license provenance differs from the pinned upstream package")

        _verify_hash(executable, item.get("executable_sha256"), engine)

        embedded_algorithm = item.get("embedded_algorithm") is True
        assets = item.get("model_assets", [])
        if not isinstance(assets, list) or any(
            not isinstance(asset, dict)
            or not isinstance(asset.get("path"), str)
            for asset in assets
        ):
            raise ValueError(engine + ": model assets must be individual files with SHA256")

        if embedded_algorithm and engine != "anime4k":
            raise ValueError(engine + ": embedded algorithm exemption forbidden")
        if engine == "anime4k":
            if not embedded_algorithm or assets:
                raise ValueError(engine + ": only the pinned Anime4KCPP CLI may use embedded algorithms")
        elif not assets:
            raise ValueError(engine + ": verified neural model assets are required")

        asset_paths = set()
        for asset in assets:
            model = Path(asset["path"])
            if not model.is_absolute() or not model.is_file():
                raise FileNotFoundError(engine + ": missing individual model asset")
            model = _inside(model, engine_root, engine, "model asset")
            if model.stat().st_size <= 0 or model.suffix.lower() not in MODEL_SUFFIXES:
                raise ValueError(engine + ": model asset is empty or has an unsupported type")
            _verify_hash(model, asset.get("sha256"), engine)
            asset_paths.add(model)

        args = _validate_args(engine, item.get("args"), engine_root)
        if engine != "anime4k":
            model_dir = Path(args[5]).resolve(strict=True)
            required_model_files = {
                item.resolve(strict=True)
                for item in model_dir.iterdir()
                if item.is_file() and item.suffix.lower() in MODEL_SUFFIXES
            }
            if not required_model_files or not required_model_files.issubset(asset_paths):
                raise ValueError(engine + ": NCNN model files are not all SHA256-pinned")

        timeout = item.get("timeout_seconds", 1800)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 1800:
            raise ValueError(engine + ": timeout_seconds is outside the safe limit")

        commands[engine] = EngineCommand(
            (str(executable), *args),
            timeout_seconds=timeout,
        )

    if len(engine_roots) != len(ENGINES):
        raise ValueError("manifest does not contain four isolated engine roots")
    if len({root.parent for root in engine_roots}) != 1:
        raise ValueError("four engines must share one provisioned install root")
    return commands
