from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
import os
import shutil
import subprocess
import tempfile

from PIL import Image
import cv2
import numpy as np

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]


class RealESRGANNCNN:
    """Small, standalone AI backend using the official Real-ESRGAN NCNN/Vulkan tool.

    No code or assets from ARM AI Image Enhancer are used here.  The backend is
    discovered beside this application or by SIGNPRINT_REALESRGAN_EXE.
    """

    def __init__(self, app_root: str | Path):
        self.app_root = Path(app_root)
        self.exe = self._find_executable()

    def _find_executable(self) -> Path | None:
        env = os.environ.get("SIGNPRINT_REALESRGAN_EXE")
        candidates: list[Path] = []
        if env:
            candidates.append(Path(env))

        # PyInstaller onedir can place data either beside the executable or under
        # _internal depending on how the build is assembled.  Search both known
        # locations plus a shallow recursive fallback so the packaged backend is
        # detected reliably.
        roots = [
            self.app_root,
            self.app_root / "tools",
            self.app_root / "_internal",
            self.app_root / "_internal" / "tools",
            Path.cwd(),
            Path.cwd() / "tools",
        ]
        for root in roots:
            candidates.append(root / "realesrgan-ncnn-vulkan.exe")

        found = shutil.which("realesrgan-ncnn-vulkan") or shutil.which("realesrgan-ncnn-vulkan.exe")
        if found:
            candidates.append(Path(found))

        seen = set()
        for p in candidates:
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            key = str(rp).lower()
            if key in seen:
                continue
            seen.add(key)
            if p.is_file():
                return p

        # Last-resort search inside the app directory.  Limit traversal to avoid
        # scanning unrelated drives.
        try:
            for p in self.app_root.rglob("realesrgan-ncnn-vulkan.exe"):
                if p.is_file():
                    return p
        except Exception:
            pass
        return None

    @property
    def available(self) -> bool:
        return bool(self.exe and self.exe.exists())

    def _run_pass(self, src: Path, dst: Path, scale: int, progress: ProgressFn, cancel: CancelFn) -> None:
        if cancel and cancel():
            raise InterruptedError("Processing cancelled")
        if not self.available:
            raise FileNotFoundError("realesrgan-ncnn-vulkan.exe not found")

        # x4plus is the balanced photo/general-purpose model.  The official NCNN
        # package carries the matching model files next to the executable.
        cmd = [
            str(self.exe), "-i", str(src), "-o", str(dst),
            "-n", "realesrgan-x4plus", "-s", str(scale),
            "-t", "0", "-f", "png",
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.exe.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
        )
        while proc.poll() is None:
            if cancel and cancel():
                proc.terminate()
                raise InterruptedError("Processing cancelled")
            line = proc.stdout.readline() if proc.stdout else ""
            if line and progress:
                progress(60, "AI Upscale: " + line.strip()[:100])
        output = ""
        if proc.stdout:
            output = proc.stdout.read() or ""
        if proc.returncode != 0:
            raise RuntimeError(f"Real-ESRGAN NCNN failed ({proc.returncode}): {output[-1000:]}")

    def upscale_array(self, rgb: np.ndarray, scale: int, progress: ProgressFn = None, cancel: CancelFn = None) -> np.ndarray:
        if scale <= 1:
            return rgb
        if not self.available:
            raise RuntimeError(
                "Real-ESRGAN AI backend ไม่พร้อมใช้งาน โปรแกรมจะไม่ fallback เป็น Lanczos "
                "เพราะจะทำให้คุณภาพต่ำกว่ารุ่นต้นแบบ"
            )

        with tempfile.TemporaryDirectory(prefix="signprint_ai_") as td:
            td = Path(td)
            src = td / "input.png"
            Image.fromarray(rgb, "RGB").save(src)

            # The x4plus model is strongest at 4x.  2x is produced by 4x AI +
            # high-quality downsampling; 8x is 4x AI followed by a 2x Lanczos
            # finishing resize.  This avoids a second hallucinating AI pass.
            ai4 = td / "ai4.png"
            if progress:
                progress(50, "กำลังขยายด้วย Real-ESRGAN")
            self._run_pass(src, ai4, 4, progress, cancel)
            arr = np.asarray(Image.open(ai4).convert("RGB"))
            if scale == 4:
                return arr
            h, w = rgb.shape[:2]
            if scale == 2:
                return cv2.resize(arr, (w * 2, h * 2), interpolation=cv2.INTER_AREA)
            if scale == 8:
                return cv2.resize(arr, (w * 8, h * 8), interpolation=cv2.INTER_LANCZOS4)
            return cv2.resize(arr, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)
