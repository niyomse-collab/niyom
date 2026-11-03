"""Safety checks for local research-only external model comparator."""
import pytest
from PIL import Image
from tools.v211_external_waifu2x_ab import build_command, validate_source


def test_command_uses_fixed_argv_and_preserves_spaces(tmp_path):
    exe = tmp_path / "reviewed engine.exe"
    exe.touch()
    weights = tmp_path / "approved models"
    weights.mkdir()
    source = tmp_path / "input.png"
    Image.new("RGB", (20, 20)).save(source)
    command = build_command(exe, source, tmp_path / "output.png", weights,
                            scale=2, noise=1)
    assert command[0] == str(exe.resolve())
    assert command[1::2] == ["-i", "-o", "-s", "-n", "-m"]
    assert command[2] == str(source.resolve())
    assert command[-1] == str(weights.resolve())
    assert validate_source(source, 2) == (20, 20)


def test_rgba_is_never_silently_flattened(tmp_path):
    source = tmp_path / "art.png"
    Image.new("RGBA", (12, 16), (255, 0, 0, 255)).save(source)
    with pytest.raises(ValueError, match="opaque 8-bit RGB"):
        validate_source(source, 2)


def test_icc_profile_is_not_silently_discarded(tmp_path):
    source = tmp_path / "image.png"
    Image.new("RGB", (12, 15), "blue").save(source, icc_profile=b"test")
    with pytest.raises(ValueError, match="ICC-managed"):
        validate_source(source, 2)


def test_diagnostic_size_is_bounded_not_production(tmp_path):
    source = tmp_path / "large.png"
    Image.new("RGB", (1100, 1100)).save(source)
    with pytest.raises(ValueError, match="16MP"):
        validate_source(source, 4)


def test_missing_binary_or_model_directory_is_rejected(tmp_path):
    source = tmp_path / "input.png"
    Image.new("RGB", (10, 10)).save(source)
    with pytest.raises(FileNotFoundError):
        build_command(tmp_path / "bad.exe", source, tmp_path / "out.png", tmp_path,
                      scale=2, noise=0)
    exe = tmp_path / "engine.exe"
    exe.touch()
    with pytest.raises(FileNotFoundError):
        build_command(exe, source, tmp_path / "out.png", tmp_path / "missing",
                      scale=2, noise=0)


def test_original_is_never_overwritten(tmp_path):
    source = tmp_path / "original.png"
    Image.new("RGB", (10, 10)).save(source)
    exe = tmp_path / "engine.exe"
    exe.touch()
    weights = tmp_path / "models"
    weights.mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        build_command(exe, source, source, weights, scale=2, noise=0)
