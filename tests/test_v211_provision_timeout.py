"""Reject invalid subprocess timeouts before provisioning any engine assets."""
import json
from pathlib import Path

import pytest

from tools.v211_four_engine_subprocess import ENGINES
from tools.v211_provision_verified_assets import provision


@pytest.mark.parametrize("bad_timeout", [0, -1, 3601, True, "1800", 1.5, None])
def test_invalid_timeout_fails_before_copy(tmp_path: Path, bad_timeout: object) -> None:
    item = {
        "executable": {"source": "/nonexistent", "sha256": "0" * 64},
        "model_assets": [{"source": "/nonexistent", "sha256": "0" * 64}],
        "args": ["{input}", "{output}"],
        "provenance": {
            "source_url": "https://example.org",
            "license_name": "test-only",
            "license_url": "https://example.org/license",
        },
        "timeout_seconds": bad_timeout,
    }
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({name: item for name in ENGINES}), encoding="utf-8")
    destination = tmp_path / "new"
    with pytest.raises(ValueError, match="timeout_seconds"):
        provision(lock, destination)
    assert not destination.exists()
