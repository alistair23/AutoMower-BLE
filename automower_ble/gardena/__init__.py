"""Opt-in Gardena app-profile support; the generic Mower API remains available."""

from .client import GardenaMower
from .model_capabilities import ModelCapabilities, identify_model

__all__ = ["GardenaMower", "ModelCapabilities", "identify_model"]
