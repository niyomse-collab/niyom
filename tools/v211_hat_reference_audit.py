"""Report HAT references in the experimental V2.1.1 tree without modifying files.

Run from a checked-out repository: python tools/v211_hat_reference_audit.py
Exit 2 when active-code references remain; historical documentation is reported
separately and does not trigger failure. This is a static audit, NOT proof of
runtime removal. The caller must still inspect dynamic imports and packaging.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TOKEN = re.compile(r"(?i)(?<![a-z0-9])hat(?:[ _-]?x4|[ _-]?assist)?(?![a-z0-9])")
CODE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".toml", ".yml", ".yaml", ".json", ".spec"}
SKIP_PREFIXES = ("docs/", "tests/", ".git/")
SELF = "tools/v211_hat_reference_audit.py"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        paths = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root
        ).decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}))
        return 3

    active, historical, unreadable = [], [], []
    for rel in paths:
        if not rel or rel == SELF:
            continue
        path = root / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in CODE_SUFFIXES and not rel.startswith("docs/"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            unreadable.append(rel)
            continue
        for line_no, line in enumerate(lines, 1):
            if TOKEN.search(line):
                item = {"path": rel, "line": line_no}
                (historical if rel.startswith(SKIP_PREFIXES) else active).append(item)
    report = {
        "status": "ERROR" if unreadable else "BLOCKED" if active else "STATIC_PASS",
        "active_references": active,
        "historical_or_test_references": historical,
        "unreadable_files": unreadable,
        "note": "Static token scan only; review dynamic loading, UI, dependencies and release workflows manually.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 3 if unreadable else 2 if active else 0


if __name__ == "__main__":
    sys.exit(main())
