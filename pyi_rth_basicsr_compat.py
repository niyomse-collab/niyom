"""Compatibility alias required by BasicSR 1.4.2 with modern TorchVision.

This does not alter the uploaded ARM processing engine or image math. It only
restores the import path expected by BasicSR:
torchvision.transforms.functional_tensor.rgb_to_grayscale
"""
import sys
import types

try:
    from torchvision.transforms.functional import rgb_to_grayscale

    name = "torchvision.transforms.functional_tensor"
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.rgb_to_grayscale = rgb_to_grayscale
        sys.modules[name] = module
except Exception:
    pass
