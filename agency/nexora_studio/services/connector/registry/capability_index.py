"""
Connector Capability Index
===========================
O(1) lookup map from capability namespace to connector IDs.
Maintained in sync with ConnectorRegistry.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from threading import RLock
from typing import Dict, List, Optional

_logger = get_logger(__name__)


class ConnectorCapabilityIndex:
    """
    In-memory index mapping capability namespaces to connector IDs.

    Updated via rebuild_from_registry() whenever the registry changes.
    Thread-safe for concurrent reads — lock held only for writes.

    Supports fallback chains: multiple connectors may provide the same namespace.
    The first registered connector for a namespace is the primary.
    """

    def __init__(self) -> None:
        # namespace → [connector_id, ...] (ordered by registration time)
        self._index: Dict[str, List[str]] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Index Management
    # ------------------------------------------------------------------

    def add(self, namespace: str, connector_id: str) -> None:
        """Register a connector as a provider of a capability namespace."""
        with self._lock:
            if namespace not in self._index:
                self._index[namespace] = []
            if connector_id not in self._index[namespace]:
                self._index[namespace].append(connector_id)
                _logger.debug(
                    "CapabilityIndex: '%s' → '%s'", namespace, connector_id
                )

    def remove(self, connector_id: str) -> int:
        """
        Remove all capability entries for a connector.
        Returns the number of namespaces removed.
        """
        with self._lock:
            removed = 0
            for namespace in list(self._index.keys()):
                if connector_id in self._index[namespace]:
                    self._index[namespace].remove(connector_id)
                    removed += 1
                    if not self._index[namespace]:
                        del self._index[namespace]
            return removed

    def rebuild(self, namespace_to_connectors: Dict[str, List[str]]) -> None:
        """
        Atomically replace the entire index.
        Called when the registry is reloaded from Odoo.
        """
        with self._lock:
            self._index = {
                ns: list(cids)
                for ns, cids in namespace_to_connectors.items()
                if cids
            }
            _logger.info(
                "CapabilityIndex rebuilt: %d namespaces indexed.", len(self._index)
            )

    def clear(self) -> None:
        """Clear the entire index."""
        with self._lock:
            self._index.clear()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_primary(self, namespace: str) -> Optional[str]:
        """
        Returns the primary (first-registered) connector_id for a namespace.
        Returns None if no connector provides this namespace.
        """
        with self._lock:
            providers = self._index.get(namespace)
            return providers[0] if providers else None

    def get_all(self, namespace: str) -> List[str]:
        """
        Returns all connector_ids for a namespace in priority order.
        Returns [] if no connector provides this namespace.
        """
        with self._lock:
            return list(self._index.get(namespace, []))

    def has_capability(self, namespace: str) -> bool:
        """Returns True if at least one connector provides this namespace."""
        with self._lock:
            return bool(self._index.get(namespace))

    def list_namespaces(self) -> List[str]:
        """Returns all indexed capability namespaces."""
        with self._lock:
            return list(self._index.keys())

    def count(self) -> int:
        """Returns the total number of indexed namespaces."""
        with self._lock:
            return len(self._index)

    def __repr__(self) -> str:
        with self._lock:
            return f"ConnectorCapabilityIndex({len(self._index)} namespaces)"
