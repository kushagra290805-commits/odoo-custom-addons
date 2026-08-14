"""
Connector Registry
==================
Part 6 of Phase 26 — Universal Connector Platform Foundation.

Single authority for all registered connectors.
Backed by nexora.connector Odoo model (read/write via env).
In-memory cache for fast capability lookups.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from threading import RLock
from typing import Dict, List, Optional

from ..domain.models import (
    Connector,
    ConnectorLifecycleState,
)
from .persistence.port import ConnectorPersistencePort

_logger = get_logger(__name__)


class ConnectorRegistry:
    """
    Central in-memory registry for all registered connectors.

    Maintains:
    - Full Connector objects (identity + state + health + config)
    - Fast capability-namespace → connector_id index
    - Persistence sync to nexora.connector Odoo model

    Thread safety:
    - All reads and writes are protected by a reentrant lock
    - Reads return copies to prevent external mutation of registry state
    """

    def __init__(self, persistence_port: Optional[ConnectorPersistencePort] = None) -> None:
        """
        Args:
            persistence_port: Adapter for backing storage.
                 If None, runs in memory-only mode (testing, bootstrap).
        """
        self._persistence = persistence_port
        self._connectors: Dict[str, Connector] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, connector: Connector) -> None:
        """
        Register a connector in the registry.
        Idempotent — re-registering with the same connector_id updates the entry.
        """
        with self._lock:
            self._connectors[connector.connector_id] = connector
            _logger.info(
                "ConnectorRegistry: registered connector '%s' (type=%s, state=%s)",
                connector.connector_id,
                connector.manifest.connector_type_id,
                connector.lifecycle_state.value,
            )

    def unregister(self, connector_id: str) -> bool:
        """
        Remove a connector from the registry.
        Returns True if removed, False if not found.
        """
        with self._lock:
            if connector_id in self._connectors:
                del self._connectors[connector_id]
                _logger.info("ConnectorRegistry: unregistered connector '%s'", connector_id)
                return True
            return False

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, connector_id: str) -> Optional[Connector]:
        """Retrieve a connector by ID. Returns None if not found."""
        with self._lock:
            return self._connectors.get(connector_id)

    def get_all(self) -> List[Connector]:
        """Returns all registered connectors."""
        with self._lock:
            return list(self._connectors.values())

    def get_by_state(self, state: ConnectorLifecycleState) -> List[Connector]:
        """Returns all connectors in a specific lifecycle state."""
        with self._lock:
            return [c for c in self._connectors.values() if c.lifecycle_state == state]

    def get_running(self) -> List[Connector]:
        """Returns all RUNNING connectors."""
        return self.get_by_state(ConnectorLifecycleState.RUNNING)

    def get_by_type(self, type_id: str) -> List[Connector]:
        """Returns all connectors of a specific type."""
        with self._lock:
            return [
                c for c in self._connectors.values()
                if c.manifest.connector_type_id == type_id
            ]

    def find_for_capability(self, namespace: str) -> Optional[Connector]:
        """
        Returns the first RUNNING connector that provides the given capability namespace.
        Returns None if no connector is running for this namespace.
        """
        with self._lock:
            for connector in self._connectors.values():
                if connector.is_running:
                    cap = connector.get_capability(namespace)
                    if cap is not None:
                        return connector
            return None

    def find_all_for_capability(self, namespace: str) -> List[Connector]:
        """
        Returns all RUNNING connectors that provide the given capability namespace.
        Useful for failover chains.
        """
        with self._lock:
            result = []
            for connector in self._connectors.values():
                if connector.is_running and connector.get_capability(namespace) is not None:
                    result.append(connector)
            return result

    def update_state(
        self,
        connector_id: str,
        new_state: ConnectorLifecycleState,
        error_message: str = "",
    ) -> bool:
        """
        Update the lifecycle state of a registered connector.
        Returns True if updated, False if connector not found.
        """
        with self._lock:
            connector = self._connectors.get(connector_id)
            if connector is None:
                _logger.warning("ConnectorRegistry.update_state: connector '%s' not found.", connector_id)
                return False
            connector.lifecycle_state = new_state
            if error_message:
                connector.error_message = error_message
            return True

    # ------------------------------------------------------------------
    # State Information
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Returns total number of registered connectors."""
        with self._lock:
            return len(self._connectors)

    def count_by_state(self, state: ConnectorLifecycleState) -> int:
        """Returns count of connectors in a specific state."""
        with self._lock:
            return sum(1 for c in self._connectors.values() if c.lifecycle_state == state)

    def get_capability_namespaces(self) -> List[str]:
        """Returns all capability namespaces provided by RUNNING connectors."""
        with self._lock:
            namespaces = set()
            for connector in self._connectors.values():
                if connector.is_running:
                    for cap in connector.get_capabilities():
                        namespaces.add(cap.namespace)
            return list(namespaces)

    def is_registered(self, connector_id: str) -> bool:
        """Returns True if the connector_id is registered."""
        with self._lock:
            return connector_id in self._connectors

    # ------------------------------------------------------------------
    # Odoo Persistence (stubbed for Phase 26)
    # ------------------------------------------------------------------

    def sync_from_odoo(self) -> int:
        """
        Load connector registrations from the nexora.connector Odoo model via the persistence port.
        Returns the number of connectors loaded.
        """
        if self._persistence is None:
            _logger.debug("ConnectorRegistry.sync_from_odoo: no persistence port, skipping sync.")
            return 0
        connectors = self._persistence.load_all_connectors()
        with self._lock:
            for connector in connectors:
                self._connectors[connector.connector_id] = connector
        _logger.info("ConnectorRegistry.sync_from_odoo: loaded %d connectors.", len(connectors))
        return len(connectors)

    def persist_to_odoo(self, connector: Connector) -> bool:
        """
        Persist a connector's state to the nexora.connector Odoo model via the persistence port.
        Returns True if persisted, False if env is unavailable.
        """
        if self._persistence is None:
            _logger.debug("ConnectorRegistry.persist_to_odoo: no persistence port — connector '%s'", connector.connector_id)
            return False
        self._persistence.save_connector(connector)
        return True

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ConnectorRegistry("
                f"total={len(self._connectors)}, "
                f"running={self.count_by_state(ConnectorLifecycleState.RUNNING)})"
            )
