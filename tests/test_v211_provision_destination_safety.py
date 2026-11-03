"""Regression: provisioning must never delete an existing directory."""
from pathlib import Path

import pytest

from tools.v211_provision_verified_assets import provision


def test_existing_empty_destination_is_not_owned_by_provisioner(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    lock = tmp_path / "lock.json"
    lock.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        provision(lock, destination)
    assert destination.is_dir()


def test_existing_nonempty_destination_is_preserved(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("do not delete", encoding="utf-8")
    lock = tmp_path / "lock.json"
    lock.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        provision(lock, destination)
    assert marker.read_text(encoding="utf-8") == "do not delete"


def test_symlink_destination_is_rejected_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("untouched", encoding="utf-8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this runner")
    lock = tmp_path / "lock.json"
    lock.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="symlink"):
        provision(lock, link)
    assert link.is_symlink()
    assert marker.read_text(encoding="utf-8") == "untouched"
