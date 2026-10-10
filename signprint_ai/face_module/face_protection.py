from __future__ import annotations

import importlib.util
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageOps

ProgressFn = Optional[Callable[[int, str], None]]
CancelFn = Optional[Callable[[], bool]]

# Keep the optional face pass conservative on very large print masters. If the
# final print image is above this limit, preserve the exact ARM output instead
# of risking a large extra memory allocation in the optional face layer.
MAX_FACE_PIXELS = 80_000_000

# Auto-detection works from a reduced preview image so adding a large banner
# does not allocate the full print-resolution face detector graph.
DETECT_MAX_SIDE = 1800


@dataclass(frozen=True)
class FaceProtectionResult:
    enabled: bool
    applied: bool
    face_count: int = 0
    detected_count: int = 0
    mode: str = "protect"
    strength: int = 35
    skipped_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "applied": self.applied,
            "face_count": self.face_count,
            "detected_count": self.detected_count,
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
    """Optional GFPGAN/FaceXLib face protection layer.

    The proven ARM/Real-ESRGAN engine is intentionally separate. Detection can
    run automatically when a file is added, while GFPGAN itself is loaded only
    when the user has explicitly selected one or more faces for protection.

    Any failure in this optional layer must leave the already-produced ARM
    result untouched.
    """

    def __init__(self):
        self._backend = None
        self._backend_device: str | None = None
        self._backend_lock = threading.Lock()

        # Detector-only helper used by the upload-time automatic scan. Keeping
        # it separate prevents UI analysis from mutating the full restoration
        # helper used later by the render worker.
        self._detector_helper = None
        self._detector_device: str | None = None
        self._detector_lock = threading.RLock()

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

    @property
    def detector_available(self) -> bool:
        try:
            return (
                importlib.util.find_spec("facexlib") is not None
                and (self.model_dir / "detection_Resnet50_Final.pth").is_file()
            )
        except Exception:
            return False

    @staticmethod
    def _effective_device(device_name: str | None) -> str:
        value = (device_name or "cpu").strip()
        # GFPGAN/FaceXLib on DirectML is not validated. Keep the optional face
        # layer on CPU there while the ARM engine can still use DirectML.
        if value.lower().startswith("dml:"):
            return "cpu"
        if value.upper() == "AUTO":
            try:
                import torch
                return "cuda:0" if torch.cuda.is_available() else "cpu"
            except Exception:
                return "cpu"
        return value

    def _make_helper(self, device):
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper

        return FaceRestoreHelper(
            1,
            face_size=512,
            crop_ratio=(1, 1),
            det_model="retinaface_resnet50",
            save_ext="png",
            use_parse=False,
            device=device,
            model_rootpath=str(self.model_dir),
        )

    def _load_detector(self, device_name: str | None = "cpu"):
        effective = self._effective_device(device_name)
        with self._detector_lock:
            if self._detector_helper is not None and self._detector_device == effective:
                return self._detector_helper

            import torch

            detector_model = self.model_dir / "detection_Resnet50_Final.pth"
            if not detector_model.is_file():
                raise FileNotFoundError(f"Missing face detector model: {detector_model}")

            helper = self._make_helper(torch.device(effective))
            self._detector_helper = helper
            self._detector_device = effective
            return helper

    def _load_backend(self, device_name: str | None):
        effective = self._effective_device(device_name)
        with self._backend_lock:
            if self._backend is not None and self._backend_device == effective:
                return self._backend

            import torch
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

            helper = self._make_helper(device)

            self._backend = {
                "network": network,
                "helper": helper,
                "torch": torch,
                "device": device,
            }
            self._backend_device = effective
            return self._backend

    def smoke_test(self, device_name: str = "cpu") -> None:
        """Lightweight packaged-backend validation for CI."""
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper  # noqa: F401
        from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean  # noqa: F401

        required = (
            self.model_dir / "GFPGANv1.4.pth",
            self.model_dir / "detection_Resnet50_Final.pth",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing packaged Face Protect model(s): " + ", ".join(missing))

    @staticmethod
    def _box_from_landmarks(landmarks, width: int, height: int):
        import numpy as np

        pts = np.asarray(landmarks, dtype=np.float32).reshape(-1, 2)
        min_xy = pts.min(axis=0)
        max_xy = pts.max(axis=0)
        center = pts.mean(axis=0)

        span_x = max(12.0, float(max_xy[0] - min_xy[0]))
        span_y = max(12.0, float(max_xy[1] - min_xy[1]))

        # Expand well beyond the 5 landmarks so the clickable rectangle covers
        # the full face rather than only eyes/nose/mouth.
        box_w = max(span_x * 2.4, span_y * 1.8, 40.0)
        box_h = max(span_y * 2.9, span_x * 2.1, 48.0)

        cx = float(center[0])
        cy = float(center[1] - 0.08 * box_h)
        x1 = max(0.0, cx - box_w / 2)
        y1 = max(0.0, cy - box_h / 2)
        x2 = min(float(width), cx + box_w / 2)
        y2 = min(float(height), cy + box_h / 2)

        return (
            int(round(x1)),
            int(round(y1)),
            int(round(x2)),
            int(round(y2)),
        )

    def detect_faces(
        self,
        image_or_path: Image.Image | str | Path,
        *,
        device_name: str | None = "cpu",
        max_side: int = DETECT_MAX_SIDE,
    ) -> list[dict]:
        """Detect faces for UI selection without loading the GFPGAN network.

        Returns original-image pixel boxes and normalized face centers. The
        normalized centers are later used to match the user's selected faces
        after ARM upscaling, even if the output dimensions differ.
        """
        if not self.detector_available:
            raise RuntimeError(
                "ไม่พบ FaceXLib/RetinaFace detector หรือไฟล์ detection_Resnet50_Final.pth"
            )

        import cv2
        import numpy as np

        close_after = False
        if isinstance(image_or_path, Image.Image):
            source = ImageOps.exif_transpose(image_or_path).convert("RGB")
        else:
            opened = Image.open(image_or_path)
            close_after = True
            source = ImageOps.exif_transpose(opened).convert("RGB")

        try:
            original_w, original_h = source.size
            scale = min(1.0, float(max_side) / max(original_w, original_h))
            if scale < 1.0:
                detect_image = source.resize(
                    (
                        max(1, round(original_w * scale)),
                        max(1, round(original_h * scale)),
                    ),
                    Image.Resampling.LANCZOS,
                )
            else:
                detect_image = source

            rgb = np.asarray(detect_image)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            # Serialize detector-helper access because FaceRestoreHelper mutates
            # internal lists on every image.
            with self._detector_lock:
                helper = self._load_detector(device_name)
                helper.clean_all()
                helper.read_image(bgr.copy())
                helper.get_face_landmarks_5()
                helper.align_warp_face()
                landmarks_list = [
                    np.asarray(face, dtype=np.float32).copy()
                    for face in helper.all_landmarks_5
                ]
                helper.clean_all()

            results: list[dict] = []
            inv_scale = 1.0 / max(scale, 1e-8)
            for index, landmarks in enumerate(landmarks_list):
                original_landmarks = landmarks * inv_scale
                box = self._box_from_landmarks(original_landmarks, original_w, original_h)
                center_x = float(original_landmarks[:, 0].mean()) / max(1, original_w)
                center_y = float(original_landmarks[:, 1].mean()) / max(1, original_h)
                results.append(
                    {
                        "index": index,
                        "box": box,
                        "center": (
                            max(0.0, min(1.0, center_x)),
                            max(0.0, min(1.0, center_y)),
                        ),
                    }
                )
            return results
        finally:
            if close_after:
                try:
                    opened.close()
                except Exception:
                    pass

    @staticmethod
    def _blend_alpha(mode: str, strength: int) -> float:
        normalized = max(0.0, min(1.0, float(strength) / 100.0))
        mode_name = str(mode).lower()
        if mode_name == "recover":
            return min(0.75, normalized)
        if mode_name == "portrait":
            # Portrait Enhance remains conservative: enough restoration to clean
            # a selected face, but preserves identity and leaves all non-face
            # pixels on the proven ARM Core path.
            return min(0.55, normalized)
        return min(0.45, normalized)

    @staticmethod
    def _match_selected_faces(landmarks_list, image_size, targets):
        import numpy as np

        width, height = image_size
        if targets is None:
            return list(range(len(landmarks_list)))
        if not targets or not landmarks_list:
            return []

        centers = []
        for landmarks in landmarks_list:
            pts = np.asarray(landmarks, dtype=np.float32).reshape(-1, 2)
            centers.append(
                (
                    float(pts[:, 0].mean()) / max(1, width),
                    float(pts[:, 1].mean()) / max(1, height),
                )
            )

        selected: list[int] = []
        unused = set(range(len(centers)))
        # A 0.20 normalized-distance gate avoids selecting a completely
        # different person if detector order changes after upscaling.
        max_dist_sq = 0.20 * 0.20
        for tx, ty in targets:
            if not unused:
                break
            best = min(
                unused,
                key=lambda i: (centers[i][0] - tx) ** 2 + (centers[i][1] - ty) ** 2,
            )
            dist_sq = (centers[best][0] - tx) ** 2 + (centers[best][1] - ty) ** 2
            if dist_sq <= max_dist_sq:
                selected.append(best)
                unused.remove(best)
        return selected

    def apply(
        self,
        image: Image.Image,
        *,
        device_name: str | None,
        mode: str = "protect",
        strength: int = 35,
        selected_targets: tuple[tuple[float, float], ...] | None = None,
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
                mode=mode,
                strength=strength,
                skipped_reason="ภาพมีขนาดใหญ่เกินขีดจำกัดหน่วยความจำของ Face Protect",
            )

        if not self.available:
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                mode=mode,
                strength=strength,
                skipped_reason="ไม่พบ GFPGAN / FaceXLib หรือโมเดลใบหน้าที่แพ็กไว้",
            )

        if progress:
            progress(0, "Face Protect · ตรวจจับใบหน้าที่เลือก")

        import cv2
        import numpy as np
        from basicsr.utils import img2tensor, tensor2img
        from torchvision.transforms.functional import normalize

        backend = self._load_backend(device_name)
        helper = backend["helper"]
        network = backend["network"]
        torch = backend["torch"]

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

        all_crops = [face.copy() for face in helper.cropped_faces]
        all_landmarks = [face.copy() for face in helper.all_landmarks_5]
        all_affine = [matrix.copy() for matrix in helper.affine_matrices]
        detected_count = len(all_crops)

        if detected_count == 0:
            helper.clean_all()
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                face_count=0,
                detected_count=0,
                mode=mode,
                strength=strength,
            )

        selected_indices = self._match_selected_faces(
            all_landmarks,
            rgb_image.size,
            selected_targets,
        )
        if not selected_indices:
            helper.clean_all()
            return rgb_image, FaceProtectionResult(
                enabled=True,
                applied=False,
                face_count=0,
                detected_count=detected_count,
                mode=mode,
                strength=strength,
                skipped_reason="ไม่พบใบหน้าที่ตรงกับตำแหน่งที่ผู้ใช้เลือก",
            )

        # Mirror the selection behavior of the original ARM face workflow: only
        # selected geometry is kept before inverse-affine paste-back.
        helper.cropped_faces = [all_crops[i].copy() for i in selected_indices]
        helper.all_landmarks_5 = [all_landmarks[i].copy() for i in selected_indices]
        helper.affine_matrices = [all_affine[i].copy() for i in selected_indices]
        helper.restored_faces = []
        helper.get_inverse_affine()

        selected_count = len(selected_indices)
        if progress:
            progress(20, f"Face Protect · เลือก {selected_count}/{detected_count} ใบหน้า")

        alpha = self._blend_alpha(mode, strength)

        for position, crop in enumerate(list(helper.cropped_faces), start=1):
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
                done = 20 + round(65 * position / max(1, selected_count))
                progress(done, f"Face Protect · ใบหน้า {position}/{selected_count}")

        result_bgr = helper.paste_faces_to_input_image()
        helper.clean_all()
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

        if progress:
            progress(100, f"Face Protect · เสร็จ {selected_count} ใบหน้า")

        return Image.fromarray(result_rgb), FaceProtectionResult(
            enabled=True,
            applied=True,
            face_count=selected_count,
            detected_count=detected_count,
            mode=mode,
            strength=strength,
        )
