"""Backward-compatible import shim for older NiyomSilp integrations.

New development must import NiyomSilpCoreAdapter from niyomsil_core_adapter.
This file contains no inference or image-processing implementation.
"""

from .niyomsil_core_adapter import NiyomSilpCoreAdapter

ARMCoreAdapter = NiyomSilpCoreAdapter

__all__ = ["NiyomSilpCoreAdapter", "ARMCoreAdapter"]
