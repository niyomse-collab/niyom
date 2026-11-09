"""Fail closed before a V2 build can delete another V2 release workspace.

The shared build script clears build/, dist/ and release/. A V2.1.1
experimental build may reuse those directories only when their existing
provenance proves they belong to a previous V2.1.1 candidate. Accepted V2
builds, V1 builds, unknown files and partial/unverifiable workspaces are
never cleaned by this guard.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_V211_VERSION = re.compile(r"^2\\.1\\.1-beta\\.\\d+$")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_PROOF_HEADER = "NIYOMSIL DESIGN v2 - VERIFIED INSTALLER BUILD PROOF"
_INSTALLER_PREFIX = "NiyomSilp-Design-v211-EXPERIMENTAL-Setup"
_ALLOWED_RELEASE_FILES = {"SHA256SUMS.txt", "CANDIDATE_PROVENANCE.json"}


class BuildWorkspaceError(ValueError):
    """The workspace contains files that this build is not allowed to clean."""


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise BuildWorkspaceError("build_info.json must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BuildWorkspaceError("existing build_info.json is unreadable") from exc
    if not isinstance(value, dict):
        raise BuildWorkspaceError("existing build_info.json is not an object")
    return value


def _verified_v211_proof(path: Path, build_info: dict) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return False
    if not lines or lines[0].strip() != _PROOF_HEADER:
        return False
    version = next(
        (line.split(":", 1)[1].strip() for line in lines
         if line.startswith("Version:")),
        "",
    )
    source_commit = next(
        (line.split(":", 1)[1].strip() for line in lines
         if line.startswith("Source commit:")),
        "",
    )
    return bool(
        _V211_VERSION.fullmatch(version)
        and version == build_info.get("version")
        and _SHA.fullmatch(source_commit)
        and source_commit.lower() == str(build_info.get("source_commit", "")).lower()
    )


def validate_v211_build_workspace(
    root: str | Path,
    requested_version: str,
) -> dict:
    """Validate that a V2 build may safely clean this workspace.

    A clean checkout is always safe. Existing build outputs may be reused only
    for another V2.1.1 beta build with matching build_info.json and BUILD_PROOF.
    No accepted V2 stable output or unknown release file is ever deleted.
    """
    root = Path(root).resolve()
    if not _V211_VERSION.fullmatch(str(requested_version)):
        # Stable V2 builds must also use a clean workspace. This prevents the
        # shared cleanup step from deleting an accepted V2 release.
        if any((root / name).exists() for name in ("build", "dist", "release", "build_info.json")):
            raise BuildWorkspaceError(
                "non-experimental V2 builds require a clean isolated workspace"
            )
        return {"status": "clean_workspace", "requested_version": requested_version}

    build_dir = root / "build"
    dist_dir = root / "dist"
    release_dir = root / "release"
    info_path = root / "build_info.json"
    proof_path = dist_dir / "NiyomsilAIEnhancer" / "BUILD_PROOF.txt"
    output_paths = (build_dir, dist_dir, release_dir)
    outputs_exist = any(path.exists() for path in output_paths)

    for path in output_paths:
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise BuildWorkspaceError(f"existing {path.name}/ must be a regular directory")

    if release_dir.is_dir():
        names = [item.name.lower() for item in release_dir.iterdir()]
        if any(name.startswith("niyomsilp-design-v1-") for name in names):
            raise BuildWorkspaceError("V1 installer files are present; refusing V2 cleanup")
        if any(name.startswith("niyomsilp-design-v2-") for name in names):
            raise BuildWorkspaceError("accepted V2 stable installer files are present; refusing cleanup")
        for item in release_dir.iterdir():
            if not item.is_file() or item.is_symlink():
                raise BuildWorkspaceError("release/ contains an unknown directory or link")
            allowed = (
                item.name.startswith(_INSTALLER_PREFIX)
                or item.name in _ALLOWED_RELEASE_FILES
            )
            if not allowed:
                raise BuildWorkspaceError(
                    f"release/ contains an unverified file: {item.name}"
                )

    if dist_dir.is_dir():
        entries = list(dist_dir.iterdir())
        if any(item.name != "NiyomsilAIEnhancer" for item in entries):
            raise BuildWorkspaceError("dist/ contains files outside the V2.1.1 application folder")
        app_dir = dist_dir / "NiyomsilAIEnhancer"
        if app_dir.exists() and (app_dir.is_symlink() or not app_dir.is_dir()):
            raise BuildWorkspaceError("dist/NiyomsilAIEnhancer must be a regular directory")

    build_info = None
    if info_path.exists():
        build_info = _read_json(info_path)
        if (
            build_info.get("channel") != "v2"
            or not _V211_VERSION.fullmatch(str(build_info.get("version", "")))
        ):
            raise BuildWorkspaceError(
                "existing build_info.json is not a V2.1.1 experimental build"
            )

    if outputs_exist:
        if build_info is None:
            raise BuildWorkspaceError(
                "existing build outputs have no V2.1.1 build_info.json provenance"
            )
        if not _verified_v211_proof(proof_path, build_info):
            raise BuildWorkspaceError(
                "existing build outputs lack a matching V2.1.1 BUILD_PROOF; "
                "use a clean isolated checkout"
            )

    return {
        "status": "verified_previous_v211_candidate" if outputs_exist else "clean_workspace",
        "requested_version": requested_version,
        "previous_version": build_info.get("version") if build_info else None,
        "previous_source_commit": build_info.get("source_commit") if build_info else None,
        "stable_v2_files_preserved": True,
        "v1_files_preserved": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--requested-version", required=True)
    args = parser.parse_args()
    try:
        report = validate_v211_build_workspace(args.root, args.requested_version)
    except BuildWorkspaceError as exc:
        print("BUILD_WORKSPACE_REFUSED: " + str(exc))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
