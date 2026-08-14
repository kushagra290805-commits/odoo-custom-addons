"""
Connector Type Registry
=======================
Maintains the registry of all known connector types.
New types are added by calling register() — no code modification required.
Thread-safe for concurrent reads (write only at startup).
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from threading import RLock
from typing import Dict, List, Optional

from .connector_types import (
    ConnectorTypeDescriptor,
    BUILTIN_CONNECTOR_TYPES,
    UNKNOWN_CONNECTOR_TYPE,
)

_logger = get_logger(__name__)


class ConnectorTypeRegistry:
    """
    Central registry of all known connector type descriptors.

    Rules:
    - Types are registered once at platform bootstrap.
    - Types may be read from any thread concurrently.
    - Types are never removed or overwritten (immutable after registration).
    - Unknown type IDs resolve to UNKNOWN_CONNECTOR_TYPE (forward compatibility).
    """

    def __init__(self) -> None:
        self._registry: Dict[str, ConnectorTypeDescriptor] = {}
        self._lock = RLock()
        self._register_builtins()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, descriptor: ConnectorTypeDescriptor) -> None:
        """
        Register a new connector type descriptor.
        Raises ValueError if the type_id is already registered.
        Must be called during platform bootstrap before any connectors are loaded.
        """
        with self._lock:
            if descriptor.type_id in self._registry:
                existing = self._registry[descriptor.type_id]
                if existing is descriptor:
                    return  # idempotent same-object re-register
                raise ValueError(
                    f"ConnectorTypeRegistry: type_id '{descriptor.type_id}' is already registered "
                    f"as '{existing.display_name}'. Types are immutable after registration."
                )
            self._registry[descriptor.type_id] = descriptor
            _logger.debug("Registered connector type: %s (%s)", descriptor.type_id, descriptor.display_name)

    def _register_builtins(self) -> None:
        """Register all built-in connector types."""
        for descriptor in BUILTIN_CONNECTOR_TYPES:
            with self._lock:
                self._registry[descriptor.type_id] = descriptor

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, type_id: str) -> ConnectorTypeDescriptor:
        """
        Resolve a type_id to its descriptor.
        Returns UNKNOWN_CONNECTOR_TYPE for unrecognized type IDs (forward compatibility).
        """
        with self._lock:
            descriptor = self._registry.get(type_id)
            if descriptor is None:
                _logger.warning(
                    "ConnectorTypeRegistry: unknown type_id '%s'. Returning UNKNOWN_CONNECTOR_TYPE.", type_id
                )
                return UNKNOWN_CONNECTOR_TYPE
            return descriptor

    def get(self, type_id: str) -> Optional[ConnectorTypeDescriptor]:
        """Returns the descriptor or None if not found (does not fall back to UNKNOWN)."""
        with self._lock:
            return self._registry.get(type_id)

    def is_registered(self, type_id: str) -> bool:
        """Returns True if the type_id is registered."""
        with self._lock:
            return type_id in self._registry

    def list_all(self) -> List[ConnectorTypeDescriptor]:
        """Returns all registered connector type descriptors."""
        with self._lock:
            return list(self._registry.values())

    def list_type_ids(self) -> List[str]:
        """Returns all registered type IDs."""
        with self._lock:
            return list(self._registry.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._registry)

    def __repr__(self) -> str:
        with self._lock:
            return f"ConnectorTypeRegistry({len(self._registry)} types: {list(self._registry.keys())})"


# ---------------------------------------------------------------------------
# Module-level singleton (initialized lazily to allow testing override)
# ---------------------------------------------------------------------------

_type_registry: Optional[ConnectorTypeRegistry] = None


def get_connector_type_registry() -> ConnectorTypeRegistry:
    """
    Returns the module-level ConnectorTypeRegistry singleton.
    Created on first access. Tests may replace this via set_connector_type_registry().
    """
    global _type_registry
    if _type_registry is None:
        _type_registry = ConnectorTypeRegistry()
    return _type_registry


def set_connector_type_registry(registry: ConnectorTypeRegistry) -> None:
    """Override the module-level registry (for testing)."""
    global _type_registry
    _type_registry = registry
