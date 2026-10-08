from __future__ import annotations

import importlib.util
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]

# Keep the optional face pass conservative on very large print masters.  If the
# image is above this limit we return the exact ARM output instead of risking a
# large extra memory allocation.
MAX_FACE_PIXELS = 80_000_000


@dataclass(frozen=True)
class FaceProtectionResult:
    enabled: bool
    applied: bool
    face_count: int = 0
    mode: str = "protect"
    strength: int = 35
    skipped_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "applied": self.applied,
            "face_count": self.face_count,
            "mode": self.mode,
            "strength": self.strength,
            "skipped_reason": self.skipped_reason,
        }


def resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


class FaceProtectionModule:
    """Optional GFPGAN/FaceXLib face restoration layer.

    The module is lazy: GFPGAN, FaceXLib and their models are not loaded until
    Face Protection is explicitly enabled.  Failures never replace or modify
    the successful ARM result; the caller can simply keep the original image.
    """

    def __init__(self):
        self._backend = None
        self._backend_device: str | None = None
        self._backend_lock = threading.Lock()

    @property
    def model_dir(self) -> Path:
        return resource_root() / "models" / "face"

    @property
    def available(self) -> bool:
        try:
            return (
                importlib.util.find_spec("gfpgan") is not None
                and importlib.util.find_spec("facexlib") is not None
                and (self.model_dir / "GFPGANv1.4.pth").is_file()
                and (self.model_dir / "detection_Resnet50_Final.pth").is_file()
            )
        except Exception:
            return False

    @staticmethod
    def _effective_device(device_name: str | None) -> str:
        value = (device_name or "cpu").strip()
        # Keep the behavior used by the ARM source: DirectML is not validated
        # for GFPGAN/FaceXLib, so face recovery uses CPU in that case.
        if value.lower().startswith("dml:"):
            return "cpu"
        if value.upper() == "AUTO":
            try:
                import torch
                return "cuda:0" if torch.cuda.is_available() else "cpu"
            except Exception:
                return "cpu"
        return value

    def _load_backend(self, device_name: str | None):
        effective = self._effective_device(device_name)
        with self._backend_lock:
            if self._backend is not None and self._backend_device == effective:
                return self._backend

            import torch
            from facexlib.utils.face_restoration_helper import FaceRestoreHelper
            from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean

            model_dir = self.model_dir
            gfpgan_model = model_dir / "GFPGANv1.4.pth"
            detector_model = model_dir / "detection_Resnet50_Final.pth"
            if not gfpgan_model.is_file():
                raise FileNotFoundError(f"Missing face model: {gfpgan_model}")
            if not detector_model.is_file():
                raise FileNotFoundError(f"Missing face detector model: {detector_model}")

            device = torch.device(effective)
            network = GFPGANv1Clean(
                out_size=512,
                num_style_feat=512,
                channel_multiplier=2,
                decoder_load_path=None,
                fix_decoder=False,
                num_mlp=8,
                input_is_latent=True,
                different_w=True,
                narrow=1,
                sft_half=True,
            )

            checkpoint = torch.load(str(gfpgan_model), map_location="cpu")
            weights = checkpoint.get("params_ema", checkpoint.get("params", checkpoint))
            network.load_state_dict(weights, strict=True)
            network.eval().to(device)

            # use_parse=False intentionally avoids the extra ParseNet model.  We
            # need only RetinaFace landmarks + the soft paste mask for this
            # conservative signage workflow.
            helper = FaceRestoreHelper(
                1,
                face_size=512,
                crop_ratio=(1, 1),
                det_model="retinaface_resnet50",
                save_ext="png",
                use_parse=False,
                device=device,
                model_rootpath=str(model_dir),
            )

            self._backend = {
                "network": network,
                "helper": helper,
                "torch": torch,
                "device": device,
            }
            self._backend_device = effective
            return self._backend

    def smoke_test(self, device_name: str = "cpu") -> None:
        """Load packaged models/imports without processing a user image."""
        self._load_backend(device_name)

    @staticmethod
    def _blend_alpha(mode: str, strength: int) -> float:
        normalized = max(0.0, min(1.0, float(strength) / 100.0))
        if str(mode).lower() == "recover":
            # Recovery may be stronger but is still capped to preserve identity.
            return min(0.75, normalized)
        # Protect is deliberately conservative: it should stabilize facial
        # structure, not invent a new face.
        return min(0.45, normalized)

    def apply(
        self,
        image: Image.Image,
        *,
        device_name: str | None,
        mode: str = "protect",
        strength: int = 35,
        progress: ProgressFn = None,
        cancel: CancelFn = None,
    ) -> tuple[Image.Image, FaceProtectionResult]:
        if cancel and cancel():
            raise InterruptedError("Processing stopped by user")

        rgb_image = image.convert("RGB")
        if rgb_image.width * rgb_image.height > MAX_FACE_PIXELS:
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                face_count=0,
                mode=mode,
                strength=strength,
                skipped_reason="ภาพมีขนาดใหญ่เกินขีดจำกัดหน่วยความจำของ Face Protect",
            )

        if not self.available:
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                face_count=0,
                mode=mode,
                strength=strength,
                skipped_reason="ไม่พบ GFPGAN / FaceXLib หรือโมเดลใบหน้าที่แพ็กไว้",
            )

        if progress:
            progress(0, "Face Protect · ตรวจจับใบหน้า")

        import cv2
        import numpy as np
        from basicsr.utils import img2tensor, tensor2img
        from torchvision.transforms.functional import normalize

        backend = self._load_backend(device_name)
        helper = backend["helper"]
        network = backend["network"]
        torch = backend["torch"]

        # Clear unused cached CUDA blocks left by the preceding ARM inference.
        try:
            if str(backend["device"]).startswith("cuda"):
                torch.cuda.empty_cache()
        except Exception:
            pass

        original_bgr = cv2.cvtColor(np.asarray(rgb_image), cv2.COLOR_RGB2BGR)
        helper.clean_all()
        helper.read_image(original_bgr.copy())
        helper.get_face_landmarks_5()
        helper.align_warp_face()

        face_count = len(helper.cropped_faces)
        if face_count == 0:
            helper.clean_all()
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                face_count=0,
                mode=mode,
                strength=strength,
                skipped_reason=None,
            )

        if progress:
            progress(20, f"Face Protect · พบ {face_count} ใบหน้า")

        helper.get_inverse_affine()
        alpha = self._blend_alpha(mode, strength)

        for index, crop in enumerate(list(helper.cropped_faces)):
            if cancel and cancel():
                helper.clean_all()
                raise InterruptedError("Processing stopped by user")

            face_tensor = img2tensor(crop / 255.0, bgr2rgb=True, float32=True)
            normalize(
                face_tensor,
                (0.5, 0.5, 0.5),
                (0.5, 0.5, 0.5),
                inplace=True,
            )
            face_tensor = face_tensor.unsqueeze(0).to(backend["device"])

            with torch.no_grad():
                restored = network(face_tensor, return_rgb=False, weight=0.5)[0]

            restored_face = tensor2img(
                restored.squeeze(0),
                rgb2bgr=True,
                min_max=(-1, 1),
            ).astype(np.uint8)

            # Blend the restored crop with the ARM crop before paste-back.  This
            # is the identity-preservation guard that keeps Protect mode mild.
            if alpha < 1.0:
                restored_face = cv2.addWeighted(
                    crop,
                    1.0 - alpha,
                    restored_face,
                    alpha,
                    0.0,
                )

            helper.add_restored_face(restored_face)

            if progress:
                done = 20 + round(65 * (index + 1) / max(1, face_count))
                progress(done, f"Face Protect · ใบหน้า {index + 1}/{face_count}")

        result_bgr = helper.paste_faces_to_input_image()
        helper.clean_all()
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

        if progress:
            progress(100, f"Face Protect · เสร็จ {face_count} ใบหน้า")

        return Image.fromarray(result_rgb), FaceProtectionResult(
            enabled=True,
            applied=True,
            face_count=face_count,
            mode=mode,
            strength=strength,
            skipped_reason=None,
        )
