"""Optional face protection module for Niyomsil Design AI Enhancer.

This package is deliberately separate from the proven ARM/Real-ESRGAN core.
When disabled, no face code is loaded or applied and the ARM output path is
unchanged.
"""

from .face_protection import FaceProtectionModule, FaceProtectionResult

__all__ = ["FaceProtectionModule", "FaceProtectionResult"]
