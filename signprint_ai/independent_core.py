"""NiyomSilp-owned runtime orchestration; third-party inference stays upstream.

Written independently for NiyomSilp Design. No ARM application modules are used.
The compatibility contract is x4plus, FP32, CUDA tiles 256 / CPU-DML tiles 128,
padding 10, and no image filters before or after model inference.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import time


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    name: str
    backend: str
    available: bool = True
    memory_mb: int | None = None


class DeviceManager:
    def __init__(self):
        import torch
        self.devices = [DeviceInfo("cpu", "CPU", "CPU")]
        if torch.cuda.is_available():
            for index in range(torch.cuda.device_count()):
                self.devices.append(DeviceInfo(
                    f"cuda:{index}", torch.cuda.get_device_name(index), "CUDA",
                    memory_mb=int(torch.cuda.get_device_properties(index).total_memory / 1048576),
                ))
        try:
            import torch_directml as dml
            for index in range(dml.device_count()):
                try:
                    name = dml.device_name(index)
                except Exception:
                    name = f"DirectML GPU {index}"
                self.devices.append(DeviceInfo(f"dml:{index}", name, "DIRECTML"))
        except Exception:
            pass  # Optional backend must not prevent CPU/CUDA startup.

    def get_devices(self):
        return list(self.devices)

    def get_device(self, device_id):
        return next((item for item in self.devices if item.device_id == device_id), None)

    def get_default_device(self):
        for backend in ("CUDA", "DIRECTML", "CPU"):
            for item in self.devices:
                if item.available and item.backend == backend:
                    return item
        raise RuntimeError("No available processing device")


def model_path():
    root = Path(__file__).resolve().parents[1]
    candidates = (root / "models" / "RealESRGAN_x4plus.pth",
                  root / "_internal" / "models" / "RealESRGAN_x4plus.pth")
    return next((path for path in candidates if path.is_file()), candidates[0])


class RealESRGANEngine:
    def __init__(self, selected):
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        self.selected = selected
        self.model_path = model_path()
        if not self.model_path.is_file():
            raise FileNotFoundError(f"ไม่พบโมเดล: {self.model_path}")
        if selected.backend == "DIRECTML":
            import torch_directml
            self.device = torch_directml.device(int(selected.device_id.split(":")[1]))
        else:
            self.device = torch.device(selected.device_id)
        network = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                          num_block=23, num_grow_ch=32, scale=4)
        self.upsampler = RealESRGANer(
            scale=4, model_path=str(self.model_path), model=network,
            tile=256 if selected.backend == "CUDA" else 128,
            tile_pad=10, pre_pad=0, half=False, device=self.device,
        )

    def device_name(self):
        return self.selected.name

    def enhance(self, input_path, output_path, scale=4, progress_callback=None, cancel_check=None):
        import torch
        import numpy as np
        from PIL import Image

        def check_cancel():
            if cancel_check and cancel_check():
                raise InterruptedError("Processing stopped by user")

        check_cancel()
        if scale not in (2, 4):
            raise ValueError("AI Scale must be 2 or 4")
        with Image.open(input_path) as source:
            original_size = source.size
            pixels = np.array(source if source.mode in ("RGB", "RGBA") else source.convert("RGB"))
        cuda = self.selected.backend == "CUDA"
        if cuda:
            torch.cuda.synchronize(self.device)
        started = time.perf_counter()
        tile = self.upsampler.tile_size
        total = math.ceil(pixels.shape[0] / tile) * math.ceil(pixels.shape[1] / tile) if tile else 1
        completed = 0

        def after_tile(_module, _inputs, _result):
            nonlocal completed
            check_cancel()
            completed += 1
            if progress_callback:
                progress_callback(min(100, round(completed * 100 / total)))

        # Cancellation works at tile boundaries even without a progress listener.
        hook = self.upsampler.model.register_forward_hook(after_tile)
        try:
            output, _ = self.upsampler.enhance(pixels, outscale=scale)
        finally:
            hook.remove()
        check_cancel()
        if cuda:
            torch.cuda.synchronize(self.device)
        elapsed = time.perf_counter() - started
        result = Image.fromarray(output)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.save(destination)
        peak = None
        if cuda:
            peak = round(torch.cuda.max_memory_allocated(self.device) / 1048576, 1)
            torch.cuda.reset_peak_memory_stats(self.device)
        return dict(input=str(input_path), output=str(destination), device=self.device_name(),
                    precision="FP32", scale=scale, input_size=original_size,
                    output_size=result.size, time_seconds=round(elapsed, 3), vram_peak_mb=peak)


class EngineManager:
    def __init__(self):
        self.device_manager = DeviceManager()
        self.engine = None

    def create_engine(self, device="AUTO"):
        selected = (self.device_manager.get_default_device() if device == "AUTO"
                    else self.device_manager.get_device(device))
        if selected is None or not selected.available:
            raise RuntimeError(f"ไม่พบ Device: {device}")
        if selected.backend not in ("CPU", "CUDA", "DIRECTML"):
            raise RuntimeError(f"Unsupported backend: {selected.backend}")
        self.engine = RealESRGANEngine(selected)
        return self.engine

    def get_engine(self):
        return self.engine if self.engine is not None else self.create_engine()
