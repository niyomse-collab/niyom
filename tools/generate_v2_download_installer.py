"""Embed verified release hashes into a small, one-file Windows installer."""
from pathlib import Path
import argparse
import hashlib
import json
import re


def generate(release_dir, repository, tag, version, output, icon):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", tag):
        raise ValueError("Invalid release tag")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-beta\.\d+)?", version):
        raise ValueError("Invalid version")
    release_dir = Path(release_dir).resolve()
    files = sorted(p for p in release_dir.glob("NiyomSilp-Design-v2-Setup*")
                   if p.suffix.lower() in (".exe", ".bin"))
    if not any(p.name == "NiyomSilp-Design-v2-Setup.exe" for p in files) or not any(p.suffix == ".bin" for p in files):
        raise ValueError("Complete offline installer EXE and BIN files are required")
    payloads, statements = [], []
    for path in files:
        if path.stat().st_size >= 2**31:
            raise ValueError("A release asset exceeds 2 GiB")
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        url = f"https://github.com/{repository}/releases/download/{tag}/{path.name}"
        payloads.append({"name": path.name, "size": path.stat().st_size, "sha256": digest, "url": url})
        statements.extend([
            "      if LocalFolder <> '' then begin",
            f"        if Lowercase(GetSHA256OfFile(AddBackslash(LocalFolder) + '{path.name}')) <> '{digest}' then",
            f"          RaiseException('ไฟล์ {path.name} ไม่ตรงกับชุดติดตั้งนี้');",
            f"        if not FileCopy(AddBackslash(LocalFolder) + '{path.name}', ExpandConstant('{{tmp}}\\{path.name}'), False) then",
            "          RaiseException('ไม่สามารถเตรียมไฟล์ติดตั้งได้');",
            "      end else",
            f"        DownloadPage.Add('{url}', '{path.name}', '{digest}');",
        ])
    template = (Path(__file__).resolve().parents[1] / "installer_v2_download.iss.in").read_text("utf-8")
    script = template.replace("@@VERSION@@", version).replace("@@OUTPUT@@", str(release_dir))
    script = script.replace("@@ICON@@", str(Path(icon).resolve())).replace("@@PAYLOADS@@", "\n".join(statements))
    output = Path(output)
    output.write_text(script, encoding="utf-8-sig")
    manifest = {"repository": repository, "tag": tag, "version": version, "payloads": payloads}
    (release_dir / "INSTALLER_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--icon", required=True)
    args = parser.parse_args()
    generate(args.release_dir, args.repository, args.tag, args.version, args.output, args.icon)
