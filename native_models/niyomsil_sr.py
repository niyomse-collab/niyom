"""NiyomSilp SR experimental architecture.

Written for NiyomSilp Design. This model has NO pretrained weights.
It is NOT yet used by the production Windows enhancer.
Torch operators, residual connections and pixel-shuffle are standard techniques.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F


MODEL_ID = "niyomsil-sr-v1"


class FeatureBlock(nn.Module):
    """Lightweight residual feature refinement; deliberately modest GPU footprint."""

    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.activation = nn.GELU()
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)

    def forward(self, x: Tensor) -> Tensor:
        return x + self.conv2(self.activation(self.conv1(x))) * 0.2


class NiyomSilpSR(nn.Module):
    """2x/4x RGB super-resolution network, suitable for training from scratch.

    Output is a bicubic RGB baseline plus a learned residual. At random
    initialization, this is not an AI quality improvement. Real weights require
    licensed training images, measurable validation and human print tests.
    """

    def __init__(self, *, scale: int = 4, channels: int = 48, blocks: int = 6):
        super().__init__()
        if scale not in (2, 4):
            raise ValueError("scale must be 2 or 4")
        if not 8 <= channels <= 256:
            raise ValueError("channels must be between 8 and 256")
        if not 1 <= blocks <= 32:
            raise ValueError("blocks must be between 1 and 32")
        self.scale = scale
        self.channels = channels
        self.blocks = blocks
        self.stem = nn.Conv2d(3, channels, 3, padding=1)
        self.body = nn.Sequential(*(FeatureBlock(channels) for _ in range(blocks)))
        self.fusion = nn.Conv2d(channels, channels, 3, padding=1)
        self.stages = nn.ModuleList()
        for _ in range(1 if scale == 2 else 2):
            self.stages.append(nn.Sequential(
                nn.Conv2d(channels, channels * 4, 3, padding=1),
                nn.PixelShuffle(2),
                nn.GELU(),
            ))
        self.output = nn.Conv2d(channels, 3, 3, padding=1)
        # Avoid significant random color shift at initialization.
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, image: Tensor) -> Tensor:
        if image.ndim != 4 or image.shape[1] != 3:
            raise ValueError("input must be NCHW RGB (3 channels)")
        baseline = F.interpolate(
            image, scale_factor=self.scale, mode="bicubic", align_corners=False
        )
        features = self.stem(image)
        features = features + self.fusion(self.body(features))
        for stage in self.stages:
            features = stage(features)
        return (baseline + self.output(features)).clamp(0, 1)


def create_model(scale: int = 4, channels: int = 48, blocks: int = 6) -> NiyomSilpSR:
    return NiyomSilpSR(scale=scale, channels=channels, blocks=blocks)
