"""Unit tests for four-engine command adapters (no checkpoints required)."""
import sys
from pathlib import Path

import pytest

from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors


def test_requires_all_four():
    with pytest.raises(ValueError, match="four"):
        make_processors({"waifu2x": EngineCommand(("echo", "{input}", "{output}"))})


def test_missing_placeholders_rejected():
    with pytest.raises(ValueError, match="output"):
        EngineCommand(("echo", "{input}"))


def test_four_real_subprocess_invocations(tmp_path):
    source = tmp_path / "source.png"
    from PIL import Image
    Image.new("RGB", (4, 4), (20, 40, 60)).save(source)
    script = "import pathlib,sys; pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    processors = make_processors(commands)
    for engine in ENGINES:
        target = tmp_path / (engine + ".png")
        processors[engine](source, target)
        with Image.open(target) as output:
            assert output.size == (4, 4)
            assert output.getpixel((0, 0)) == (20, 40, 60)
