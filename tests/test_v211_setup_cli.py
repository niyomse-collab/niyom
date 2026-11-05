"""Installer-time four-engine setup command tests; no network or real model runs."""
from pathlib import Path

import pytest

from signprint_ai import v211_auto_setup
from signprint_ai import v211_setup_cli


def test_installer_setup_accepts_exactly_four_verified_engines(monkeypatch):
    expected = {"real_esrgan", "waifu2x", "real_cugan", "anime4k"}
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "installed_for_offline_qa",
            "verified_engine_names": sorted(expected),
            "quality_certified": False,
        },
    )
    result = v211_setup_cli.install_for_offline_use()
    assert set(result["verified_engine_names"]) == expected
    assert result["quality_certified"] is False


def test_installer_setup_rejects_partial_or_unverified_engine_set(monkeypatch):
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "installed_for_offline_qa",
            "verified_engine_names": ["real_esrgan", "waifu2x", "real_cugan"],
        },
    )
    with pytest.raises(RuntimeError, match="exactly the required engines"):
        v211_setup_cli.install_for_offline_use()


def test_installer_setup_rejects_unknown_terminal_status(monkeypatch):
    monkeypatch.setattr(
        v211_auto_setup,
        "provision_after_consent",
        lambda: {
            "status": "failed",
            "verified_engine_names": [
                "real_esrgan", "waifu2x", "real_cugan", "anime4k"
            ],
        },
    )
    with pytest.raises(RuntimeError, match="completed state"):
        v211_setup_cli.install_for_offline_use()


def test_command_is_dispatched_before_editor_import():
    root = Path(__file__).resolve().parents[1]
    source = (root / "run.py").read_text(encoding="utf-8")
    assert source.index("--provision-v211-four-ai") < source.index(
        "from signprint_ai.app_v2 import main"
    )
    assert "signprint_ai.v211_setup_cli" in source
