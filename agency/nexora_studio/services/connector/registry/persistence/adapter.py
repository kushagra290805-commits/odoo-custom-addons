"""
Connector Persistence Adapter
=============================
Part 3 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class ConnectorPersistenceAdapter(ABC):
    """
    Abstract Adapter for underlying data stores (Odoo ORM, memory, etc).
    The PersistenceService relies on this to execute primitive DB operations.
    """

    @abstractmethod
    def read_connector_record(self, connector_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def write_connector_record(self, connector_id: str, data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def fetch_all_connectors(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_connector_record(self, connector_id: str) -> bool:
        pass
