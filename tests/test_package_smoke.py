"""The packaged Windows EXE must exit promptly and expose diagnostic failures."""
import json

from signprint_ai import package_smoke


def test_package_smoke_returns_nonzero_and_writes_traceback(monkeypatch, tmp_path):
    def broken(_folder):
        raise ValueError("simulated packaged processing failure")

    monkeypatch.setattr(package_smoke, "_run", broken)
    assert package_smoke.run(tmp_path) == 1
    message = (tmp_path / "package-smoke-error.txt").read_text(encoding="utf-8")
    assert "ValueError: simulated packaged processing failure" in message
    assert not (tmp_path / "package-smoke.json").exists()


def test_package_smoke_returns_zero_with_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(package_smoke, "_run", lambda _folder: {"passed": True})
    assert package_smoke.run(tmp_path) == 0
    assert json.loads((tmp_path / "package-smoke.json").read_text(encoding="utf-8"))["passed"]
