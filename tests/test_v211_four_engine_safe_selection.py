"""Contract tests for conservative four-engine selection (no fake AI inference)."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.v211_four_engine_coordinator import ENGINES
from tools.v211_four_engine_safe_selection import select_conservative_candidate


def _write(path: Path, pixels: np.ndarray, icc: bytes | None = None):
    kwargs = {"icc_profile": icc} if icc is not None else {}
    Image.fromarray(pixels, "RGBA").save(path, **kwargs)


def test_four_engine_selection_preserves_alpha_and_uses_fallback(tmp_path):
    src = np.zeros((4, 4, 4), dtype=np.uint8)
    src[..., :3] = 100
    src[..., 3] = 255
    src[0, 0, 3] = 0
    source = tmp_path / "source.png"
    _write(source, src)
    v2 = np.repeat(np.repeat(src, 2, axis=0), 2, axis=1)
    # Match the coordinator's exact LANCZOS alpha contract.
    v2[..., 3] = np.asarray(Image.fromarray(src[..., 3], "L").resize(
        (8, 8), Image.Resampling.LANCZOS))
    reference = tmp_path / "v2.png"
    _write(reference, v2)
    candidates = {}
    for engine in ENGINES:
        candidate = tmp_path / (engine + ".png")
        changed = v2.copy()
        changed[..., :3] = 220
        _write(candidate, changed)
        candidates[engine] = candidate
    output = tmp_path / "selected.png"
    result = select_conservative_candidate(source, reference, candidates, output)
    assert result["selected"] == "v2_fallback"
    assert np.array_equal(np.asarray(Image.open(output)), v2)
    assert result["quality_certified"] is False


def test_four_engine_selection_requires_every_engine(tmp_path):
    with pytest.raises(ValueError, match="four"):
        select_conservative_candidate(tmp_path / "missing.png",
                                      tmp_path / "v2.png", {}, tmp_path / "out.png")
