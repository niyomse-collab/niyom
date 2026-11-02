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
    source = tmp_path / "source.txt"
    source.write_text("sample", encoding="utf-8")
    script = "import pathlib,sys; pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())"
    commands = {
        engine: EngineCommand((sys.executable, "-c", script, "{input}", "{output}"))
        for engine in ENGINES
    }
    processors = make_processors(commands)
    for engine in ENGINES:
        target = tmp_path / (engine + ".txt")
        processors[engine](source, target)
        assert target.read_bytes() == b"sample"
