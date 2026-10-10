"""External ICC selection for NiyomSilp experiments; no bundled profiles.

User-provided Adobe/printshop ICC is read into memory from disk or ZIP.
No source profile bytes are copied into this public repository or renamed.
A listed profile's *embedded ICC description*, not its filename, is its identity.
The current Windows GUI is NOT changed by this module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import ImageCms

MAX_PROFILE_BYTES = 10_000_000
MAX_ZIP_ENTRIES = 256
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 128_000_000


@dataclass(frozen=True)
class ICCChoice:
    """One item a future user-facing profile selector could display."""

    description: str
    color_space: str
    device_class: str
    sha256: str
    source_member: str | None
    filename: str


def _verify_profile(blob: bytes, name: str, member: str | None) -> ICCChoice:
    if not blob or len(blob) > MAX_PROFILE_BYTES:
        raise ValueError("ICC profile is empty or too large")
    try:
        profile = ImageCms.ImageCmsProfile(BytesIO(blob))
        desc = ImageCms.getProfileDescription(profile).strip()
        space = str(profile.profile.xcolor_space).strip().upper()
        cls = str(profile.profile.device_class).strip().lower()
    except Exception as exc:
        raise ValueError(f"Invalid ICC profile: {name}: {exc}") from exc
    if space not in {"RGB", "CMYK", "GRAY", "LAB", "XYZ"}:
        raise ValueError(f"Unsupported ICC color space: {space}")
    return ICCChoice(
        description=desc or "Unnamed ICC profile",
        color_space=space,
        device_class=cls,
        sha256=hashlib.sha256(blob).hexdigest(),
        source_member=member,
        filename=name,
    )


def _zip_entries(archive: ZipFile):
    entries = archive.infolist()
    if len(entries) > MAX_ZIP_ENTRIES:
        raise ValueError("Too many ZIP entries")
    if sum(item.file_size for item in entries) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError("ZIP expands beyond allowed profile catalog size")
    for info in entries:
        if info.is_dir() or not info.filename.lower().endswith((".icc", ".icm")):
            continue
        # No extraction. Reject traversal and ignore Mac Finder resource metadata.
        path_parts = info.filename.replace("\\", "/").split("/")
        if ".." in path_parts or info.filename.startswith("/") or "__MACOSX" in path_parts:
            continue
        if info.file_size > MAX_PROFILE_BYTES:
            raise ValueError("An ICC profile is larger than the safety cap")
        yield info


def list_external_profiles(source: str | Path) -> list[ICCChoice]:
    """Inspect user-chosen ICC file, directory or ZIP, *without extracting*."""
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)
    matches: list[ICCChoice] = []
    if path.is_file() and path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            for info in _zip_entries(archive):
                blob = archive.read(info)
                matches.append(_verify_profile(blob, Path(info.filename).name, info.filename))
    elif path.is_file() and path.suffix.lower() in {".icc", ".icm"}:
        if path.stat().st_size > MAX_PROFILE_BYTES:
            raise ValueError("ICC profile exceeds allowed size")
        matches.append(_verify_profile(path.read_bytes(), path.name, None))
    elif path.is_dir():
        files = sorted(
            entry for entry in path.rglob("*")
            if entry.is_file() and not entry.is_symlink()
            and entry.suffix.lower() in {".icc", ".icm"}
        )
        if len(files) > MAX_ZIP_ENTRIES:
            raise ValueError("Too many ICC files")
        for entry in files:
            if entry.stat().st_size > MAX_PROFILE_BYTES:
                raise ValueError("ICC profile exceeds allowed size")
            matches.append(_verify_profile(entry.read_bytes(), entry.name, str(entry.relative_to(path))))
    else:
        raise ValueError("Supply .icc/.icm, a directory, or a ZIP of ICC profiles")
    return sorted(matches, key=lambda p: (p.color_space, p.description, p.filename))


def read_cmyk_profile(source: str | Path, description: str) -> bytes:
    """Pick by the exact embedded description, fail if ambiguous or not CMYK."""
    path = Path(source)
    listed = [item for item in list_external_profiles(path) if item.description == description]
    if len(listed) != 1:
        raise ValueError("Select one unique ICC profile by its embedded description")
    selected = listed[0]
    if selected.color_space != "CMYK" or selected.device_class != "prtr":
        raise ValueError("Selected profile is not a CMYK printer/output profile")
    if path.is_dir():
        blob = (path / selected.source_member).read_bytes()
    elif path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            blob = archive.read(selected.source_member)
    else:
        blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != selected.sha256:
        raise ValueError("Selected ICC changed since discovery")
    return blob



def read_cmyk_profile_by_sha(source: str | Path, sha256: str) -> bytes:
    """Unambiguously select a CMYK printer ICC by digest, never by filename.

    Returned bytes remain in memory. For ZIP archives no files are extracted.
    The digest is checked again to catch archive changes between list and read.
    """
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256.lower()):
        raise ValueError("Invalid ICC SHA-256 identifier")
    path = Path(source)
    found = [item for item in list_external_profiles(path)
             if item.sha256.lower() == sha256.lower()]
    if len(found) != 1:
        raise ValueError("Choose one unique ICC profile SHA-256")
    selected = found[0]
    if selected.color_space != "CMYK" or selected.device_class != "prtr":
        raise ValueError("Selected ICC is not a CMYK printer profile")
    if path.is_dir():
        blob = (path / selected.source_member).read_bytes()
    elif path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            blob = archive.read(selected.source_member)
    else:
        blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != sha256.lower():
        raise ValueError("ICC source changed since selected")
    return blob

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="List user-provided ICC profiles without copying them")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    profiles = list_external_profiles(args.source)
    print(json.dumps({
        "total": len(profiles),
        "cmyk": sum(p.color_space == "CMYK" for p in profiles),
        "rgb": sum(p.color_space == "RGB" for p in profiles),
        "profiles": [asdict(p) for p in profiles],
        "disclaimer": "Only generic ICC catalog identification; no shop RIP calibration is implied.",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
