"""Provision the four official Windows AI engine packages for *local QA only*.

No customer image, weight, DLL or executable is added to git or to the V2 installer.
The archives are checked against published or independently observed CI SHA256
values BEFORE extraction. The output manifest is used only for explicit QA.
This does NOT certify inference, visual quality or redistribution rights.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from tools.v211_official_assets_audit import (
    PACKAGES, audit_archive, download_archive, file_sha256, verify_archive_hash,
)

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
MODEL_SUFFIXES = {".bin", ".param", ".onnx", ".pth", ".safetensors", ".weights"}


def safe_extract_zip(archive_path: Path, target: Path) -> None:
    """Extract an already audited ZIP without following links or escaping root."""
    audit_archive(archive_path)
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            relative = PurePosixPath(info.filename.replace("\\", "/"))
            destination = target.joinpath(*relative.parts)
            if not destination.resolve().is_relative_to(root):
                raise ValueError("unsafe archive destination")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Refuse to overwrite any existing files, including archive
                # entries that collide under case-insensitive Windows paths.
                with archive.open(info) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)


def find_single(root: Path, basename: str) -> Path:
    found = [p for p in root.rglob("*") if p.is_file() and p.name.lower() == basename.lower()]
    if len(found) != 1:
        raise ValueError("expected exactly one " + basename + ", found " + str(len(found)))
    return found[0].resolve()


def model_files(root: Path) -> list[Path]:
    return sorted(
        p.resolve() for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES
    )


def find_model_folder(executable: Path, model_file_paths: list[Path], folder: str) -> Path:
    # Upstream NCNN ZIP structures may have a single version-name directory.
    # Select only the verified folder with the exact expected basename.
    matches = sorted({p.parent for p in model_file_paths if p.parent.name.lower() == folder.lower()})
    matches = [p for p in matches if p.is_relative_to(executable.parent)]
    if len(matches) != 1:
        raise ValueError("missing or ambiguous model directory: " + folder)
    directory = matches[0]
    if not any(p.suffix.lower() == ".param" for p in directory.iterdir()):
        raise ValueError("model directory lacks NCNN parameter file: " + folder)
    if not any(p.suffix.lower() == ".bin" for p in directory.iterdir()):
        raise ValueError("model directory lacks NCNN binary weights: " + folder)
    return directory


def manifest_entry(engine: str, directory: Path, package: dict, digest: dict) -> dict:
    exe = find_single(directory, EXECUTABLES[engine])
    assets = model_files(directory)
    embedded = engine == "anime4k"
    if embedded:
        if assets:
            raise ValueError("unexpected external Anime4K model assets need manual review")
        argv = ["-i", "{input}", "-o", "{output}", "-f", "2"]
    else:
        if not assets:
            raise ValueError(engine + ": no real model assets in upstream archive")
        folder = find_model_folder(exe, assets, MODEL_DIRECTORIES[engine])
        if engine == "real_esrgan":
            args = ["-n", "realesrgan-x4plus", "-s", "2"]
        elif engine == "waifu2x":
            args = ["-n", "2", "-s", "2"]
        else:
            args = ["-n", "1", "-s", "2"]
        argv = ["-i", "{input}", "-o", "{output}", "-m", str(folder), *args, "-t", "128"]
    entry = {
        "executable": str(exe),
        "executable_sha256": file_sha256(exe),
        "model_assets": [{"path": str(p), "sha256": file_sha256(p)} for p in assets],
        "args": argv,
        "timeout_seconds": 1800,
        "provenance": {
            "source_url": package["url"],
            "license_name": package["license"],
            "license_url": package["license_url"],
        },
        "qa_notice": "research_only; 2x inference not verified; manual rights review required",
        "archive_sha256": digest["archive_sha256"],
    }
    if embedded:
        entry["embedded_algorithm"] = True
    return entry


def provision_from_archives(archives: Path, install_dir: Path, manifest_path: Path) -> dict:
    """Use locally held, hash-verified ZIPs (never run downloaded executables)."""
    archives = Path(archives).resolve()
    install_dir = Path(install_dir).resolve()
    manifest_path = Path(manifest_path).resolve()
    # Validate EVERYTHING before extracting any executable.
    verified = {}
    for engine, package in PACKAGES.items():
        zippath = archives / (engine + ".zip")
        if not zippath.is_file():
            raise FileNotFoundError("missing official " + engine + ".zip")
        digest = verify_archive_hash(zippath, package.get("release_sha256"),
                                     package.get("observed_sha256"))
        audit_archive(zippath)
        verified[engine] = (zippath, digest)
    install_dir.mkdir(parents=True, exist_ok=True)
    if any((install_dir / engine).exists() for engine in PACKAGES):
        raise FileExistsError("existing installation detected; use a new empty QA directory")
    if manifest_path.exists():
        raise FileExistsError("manifest already exists; refusing to overwrite")

    manifest = {}
    for engine, package in PACKAGES.items():
        zippath, digest = verified[engine]
        with tempfile.TemporaryDirectory(dir=install_dir, prefix=".pending-") as td:
            stage = Path(td) / "tree"
            safe_extract_zip(zippath, stage)
            # The final directory must be known BEFORE paths are recorded.
            final = install_dir / engine
            # Do not move files after their hashes are generated.
            stage.rename(final)
        manifest[engine] = manifest_entry(engine, final, package, digest)

    # The manifest is created last; a failed install never produces an
    # apparently approved four-engine manifest.
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8") as dest:
        json.dump(manifest, dest, indent=2, ensure_ascii=False)
    return {
        "real_inference_verified": False,
        "quality_certified": False,
        "license_redistribution_approved": False,
        "manifest": str(manifest_path),
        "engines": list(manifest),
        "two_x_output_only": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--download-missing", action="store_true")
    args = parser.parse_args()
    if args.download_missing:
        for name, package in PACKAGES.items():
            path = args.archives_dir / (name + ".zip")
            if not path.exists():
                download_archive(package["url"], path)
    print(json.dumps(provision_from_archives(args.archives_dir, args.install_dir, args.manifest),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
