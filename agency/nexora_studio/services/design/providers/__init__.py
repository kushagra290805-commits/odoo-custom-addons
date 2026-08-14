# -*- coding: utf-8 -*-
"""
Provider Interface & Multi-Renderer Foundation Package

Exports the provider contract, context models, capability registries, and functional
rendering engine implementations (e.g., ReactRenderingProvider).
"""

from .rendering_provider import (
    RenderingProvider,
    ProviderCapabilityModel,
    ProviderVersioning,
    ProviderMetadata,
    RenderingContext,
)
from .provider_registry import RenderingProviderRegistry

# Lazy export or direct import of ReactRenderingProvider
def __getattr__(name):
    if name == "ReactRenderingProvider":
        from .react_provider import ReactRenderingProvider
        return ReactRenderingProvider
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "RenderingProvider",
    "ProviderCapabilityModel",
    "ProviderVersioning",
    "ProviderMetadata",
    "RenderingContext",
    "RenderingProviderRegistry",
    "ReactRenderingProvider",
]
