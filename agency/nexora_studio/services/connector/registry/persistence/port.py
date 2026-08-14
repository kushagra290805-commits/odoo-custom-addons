"""
Connector Persistence Port
==========================
Part 3 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from ...domain.models import Connector, ConnectorManifest

class ConnectorPersistencePort(ABC):
    """
    Abstract Port for connector persistence.
    The Runtime depends entirely on this interface, shielding it from ORM/Database details.
    """

    @abstractmethod
    def save_connector(self, connector: Connector) -> bool:
        """Saves a full connector aggregate state."""

    @abstractmethod
    def get_connector(self, connector_id: str) -> Optional[Connector]:
        """Loads a connector aggregate by ID."""

    @abstractmethod
    def load_all_connectors(self) -> List[Connector]:
        """Loads all registered connectors."""

    @abstractmethod
    def save_manifest(self, manifest: ConnectorManifest) -> bool:
        """Saves a connector manifest explicitly."""

    @abstractmethod
    def delete_connector(self, connector_id: str) -> bool:
        """Deletes a connector and all its state."""
