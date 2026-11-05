"""Audit official four-engine Windows archives without executing or redistributing them.

Downloads official release ZIPs into an ephemeral CI directory, checks release
SHA-256 when GitHub publishes one, reports older unpinned archives for review,
and inspects candidate EXE and model filenames. THIS IS NOT INFERENCE PROOF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile


PACKAGES = {
    "real_esrgan": {
        "release": "v0.2.5.0",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
        "release_sha256": None,  # Upstream release API has no digest.
        "observed_sha256": "abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d",  # Reproducible Windows Actions audit 2026-11-03.
        "license": "MIT (upstream repository LICENSE; verify model-weights rights)",
        "license_url": "https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/blob/master/LICENSE",
    },
    "waifu2x": {
        "release": "20250915",
        "url": "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20250915/waifu2x-ncnn-vulkan-20250915-windows.zip",
        "release_sha256": "7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87",
        "license": "MIT (verify included models' third-party rights)",
        "license_url": "https://github.com/nihui/waifu2x-ncnn-vulkan/blob/master/LICENSE",
    },
    "real_cugan": {
        "release": "20220728",
        "url": "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/realcugan-ncnn-vulkan-20220728-windows.zip",
        "release_sha256": None,  # Upstream release API has no digest.
        "observed_sha256": "c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01",  # Reproducible Windows Actions audit 2026-11-03.
        "license": "MIT (verify included model-weights rights)",
        "license_url": "https://github.com/nihui/realcugan-ncnn-vulkan/blob/master/LICENSE",
    },
    "anime4k": {
        "release": "v3.2.0",
        "url": "https://github.com/TianZerL/Anime4KCPP/releases/download/v3.2.0/Anime4KCPP-CLI-v3.2.0-x64-MSVC.zip",
        "release_sha256": "82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19",
        "license": "GPL-3.0 (no redistribution or installer bundling approved)",
        "license_url": "https://github.com/TianZerL/Anime4KCPP/blob/master/LICENSE",
    },
}
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive_hash(path: Path, expected: str | None, observed_pin: str | None = None) -> dict:
    actual = file_sha256(path)
    if expected is not None:
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("invalid release SHA-256 pin")
        if actual != expected:
            raise ValueError("official release SHA-256 mismatch: " + path.name)
    if observed_pin is not None:
        if len(observed_pin) != 64 or any(c not in "0123456789abcdef" for c in observed_pin):
            raise ValueError("invalid prior-audit SHA-256 pin")
        if actual != observed_pin:
            raise ValueError("Windows archive changed since independently recorded CI audit")
    return {
        "archive_sha256": actual,
        "matches_recorded_ci_sha256": observed_pin is not None and actual == observed_pin,
        "release_digest_published": expected is not None,
        "release_digest_verified": expected is not None and actual == expected,
        "requires_independent_digest_approval": expected is None,
    }


def audit_archive(path: Path) -> dict:
    if not zipfile.is_zipfile(path):
        raise ValueError("not a ZIP archive")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 20000:
            raise ValueError("ZIP contains too many files")
        if sum(x.file_size for x in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP uncompressed size exceeds audit limit")
        names = []
        seen = set()
        for info in members:
            p = PurePosixPath(info.filename.replace("\\", "/"))
            normalized = p.as_posix()
            # Reject Windows drive/UNC paths, ambiguous names and symlinks before
            # any downstream extractor can be allowed to consume this archive.
            if (p.is_absolute() or ".." in p.parts or not p.parts
                    or any(part in ("", ".") for part in p.parts)
                    or ":" in p.parts[0] or normalized.startswith("//")):
                raise ValueError("archive contains unsafe path")
            # Windows silently aliases trailing dots/spaces, rejects device names,
            # and interprets ':' as an alternate data stream in any component.
            # Reject these before extraction rather than trusting POSIX ZIP names.
            reserved = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)), *("LPT" + str(i) for i in range(1, 10))}
            if any(
                part.endswith((".", " ")) or ":" in part
                or part.split(".", 1)[0].upper() in reserved
                or any(ord(ch) < 32 or ch in '<>"|?*' for ch in part)
                for part in p.parts
            ):
                raise ValueError("archive contains unsafe Windows path")
            key = normalized.rstrip("/").casefold()
            if key in seen:
                raise ValueError("archive contains duplicate Windows path")
            seen.add(key)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError("archive contains symbolic link")
            if not info.is_dir():
                names.append(normalized)
    executables = sorted(n for n in names if n.lower().endswith(".exe"))
    # NCNN model files and common neural-network formats; do not pretend
    # that a filename alone proves a working checkpoint or license.
    model_files = sorted(n for n in names if n.lower().endswith(
        (".param", ".bin", ".onnx", ".pth", ".safetensors", ".weights")
    ) and not n.lower().endswith((".dll.bin",)))
    notices = sorted(n for n in names if any(
        key in PurePosixPath(n).name.lower()
        for key in ("license", "copying", "third_party", "notice")
    ))
    return {
        "entries": len(names),
        "candidate_executables": executables[:50],
        "model_or_binary_files_sample": model_files[:80],
        "model_or_binary_file_count": len(model_files),
        "license_and_notice_files": notices[:50],
        "archive_member_audit_passed": True,
    }


def download_archive(
    url: str,
    target: Path,
    expected_sha256: str | None = None,
    observed_sha256: str | None = None,
) -> dict:
    """Download, verify and audit an archive before atomically publishing it.

    Bytes are streamed to a same-directory temporary file. A failed network
    transfer, digest check or ZIP audit never truncates a previously verified
    archive at the target path. The temporary file is removed on every exit.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="." + target.name + ".", suffix=".part", dir=target.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    request = urllib.request.Request(
        url, headers={"User-Agent": "NiyomSilp-v211-asset-provenance-QA"}
    )
    downloaded = 0
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw_length = getattr(response, "headers", {}).get("Content-Length")
            expected_length = None
            if raw_length:
                try:
                    expected_length = int(raw_length)
                except (TypeError, ValueError):
                    raise ValueError("invalid archive Content-Length")
                if expected_length < 0 or expected_length > MAX_ARCHIVE_BYTES:
                    raise ValueError("archive exceeds download limit")
            with temporary.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_ARCHIVE_BYTES:
                        raise ValueError("archive exceeded download limit")
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())

        if downloaded == 0:
            raise ValueError("empty official archive")
        if expected_length is not None and downloaded != expected_length:
            raise ValueError("incomplete archive download")
        if not zipfile.is_zipfile(temporary):
            raise ValueError("downloaded archive is not a ZIP archive")

        digest = verify_archive_hash(
            temporary, expected_sha256, observed_sha256
        )
        audit_archive(temporary)
        # Same-directory replace is atomic on the target filesystem. Existing
        # archives remain untouched until every validation above has passed.
        os.replace(temporary, target)
        return digest
    finally:
        temporary.unlink(missing_ok=True)


def audit_official_releases(destination: Path, report_path: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "purpose": "official Windows archive provenance audit only",
        "all_four_real_inference_proven": False,
        "model_weights_and_license_certified": False,
        "included_in_customer_installer": False,
        "packages": {},
    }
    for name, package in PACKAGES.items():
        target = destination / (name + ".zip")
        entry = {
            "release": package["release"],
            "source_url": package["url"],
            "license_name": package["license"],
            "license_url": package["license_url"],
            "verified_for_inference": False,
        }
        try:
            download_archive(package["url"], target, package.get("release_sha256"), package.get("observed_sha256"))
            entry.update(verify_archive_hash(target, package["release_sha256"], package.get("observed_sha256")))
            entry.update(audit_archive(target))
            entry["status"] = "archive_audited_not_inference_verified"
        except Exception as exc:
            entry.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:240]})
        report["packages"][name] = entry
    report["all_archives_audited"] = all(
        p["status"] == "archive_audited_not_inference_verified"
        for p in report["packages"].values()
    )
    report["all_archives_match_release_or_recorded_hash"] = all(
        p.get("release_digest_verified", False) or p.get("matches_recorded_ci_sha256", False)
        for p in report["packages"].values()
    )
    report["all_upstream_digests_pinned"] = all(
        p.get("release_digest_verified", False) for p in report["packages"].values()
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = audit_official_releases(args.download_dir, args.report)
    print(json.dumps({
        "all_archives_audited": report["all_archives_audited"],
        "all_upstream_digests_pinned": report["all_upstream_digests_pinned"],
        "all_archives_match_release_or_recorded_hash": report["all_archives_match_release_or_recorded_hash"],
        "packages": {k: v["status"] for k, v in report["packages"].items()},
        "real_inference_verified": False,
    }, indent=2))
    if not report["all_archives_audited"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
