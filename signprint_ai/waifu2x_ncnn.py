"""Optional Waifu2x NCNN/Vulkan backend for the V2-based experimental branch.

Place the official waifu2x-ncnn-vulkan executable and its model directories
beside the app (or set SIGNPRINT_WAIFU2X_EXE). No downloads or model
substitutions occur silently.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image


class Waifu2xNCNN:
    def __init__(self, app_root: str | Path):
        root = Path(app_root)
        name = "waifu2x-ncnn-vulkan.exe" if os.name == "nt" else "waifu2x-ncnn-vulkan"
        env = os.environ.get("SIGNPRINT_WAIFU2X_EXE")
        candidates = ([Path(env)] if env else []) + [
            root / name, root / "tools" / name,
            root / "_internal" / name, root / "_internal" / "tools" / name,
        ]
        found = shutil.which("waifu2x-ncnn-vulkan")
        if found:
            candidates.append(Path(found))
        self.exe = next((p.resolve() for p in candidates if p.is_file()), None)

    @property
    def available(self) -> bool:
        return self.exe is not None and self.exe.is_file()

    def upscale_array(self, rgb: np.ndarray, scale: int, progress=None, cancel=None) -> np.ndarray:
        if scale not in (2, 4):
            raise ValueError("Waifu2x supports only 2x or 4x in this experimental adapter")
        if not self.available:
            raise RuntimeError("Waifu2x NCNN executable missing; no fake resize fallback")
        if cancel and cancel():
            raise InterruptedError("Processing cancelled")
        h, w = rgb.shape[:2]
        with tempfile.TemporaryDirectory(prefix="niyomsilp_waifu2x_") as tmp:
            src, dst = Path(tmp) / "input.png", Path(tmp) / "output.png"
            Image.fromarray(rgb, "RGB").save(src)
            # NCNN Waifu2x supports 2x natively; run two passes for 4x.
            current = src
            for step in range(1 if scale == 2 else 2):
                if cancel and cancel():
                    raise InterruptedError("Processing cancelled")
                target = dst if step == (0 if scale == 2 else 1) else Path(tmp) / "intermediate.png"
                cmd = [str(self.exe), "-i", str(current), "-o", str(target), "-s", "2", "-n", "0", "-f", "png"]
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                proc = subprocess.Popen(cmd, cwd=str(self.exe.parent),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        creationflags=flags)
                try:
                    while proc.poll() is None:
                        if cancel and cancel():
                            proc.terminate()
                            proc.wait(timeout=10)
                            raise InterruptedError("Processing cancelled")
                        import time
                        time.sleep(0.1)
                    log = proc.stdout.read() if proc.stdout else b""
                    if proc.returncode != 0:
                        raise RuntimeError(f"Waifu2x failed ({proc.returncode}): {log[-1000:].decode(errors='replace')}")
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
                if not target.is_file():
                    raise RuntimeError("Waifu2x returned without output image")
                current = target
                if progress:
                    progress(40 + step * 20, "Waifu2x AI upscale")
            with Image.open(dst) as img:
                arr = np.asarray(img.convert("RGB")).copy()
            if arr.shape[:2] != (h * scale, w * scale):
                raise RuntimeError("Waifu2x output dimensions mismatch")
            return arr
