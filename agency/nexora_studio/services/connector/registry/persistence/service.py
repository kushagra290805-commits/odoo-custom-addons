"""
Connector Persistence Service
=============================
Part 3 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import List, Optional

from ...domain.models import Connector, ConnectorManifest
from .port import ConnectorPersistencePort
from .adapter import ConnectorPersistenceAdapter

_logger = get_logger(__name__)


class ConnectorPersistenceService(ConnectorPersistencePort):
    """
    Implements the Persistence Port.
    Orchestrates persistence logic using an injected adapter.
    """

    def __init__(self, adapter: ConnectorPersistenceAdapter):
        self._adapter = adapter

    def save_connector(self, connector: Connector) -> bool:
        """Translates a domain Connector to a dict for the adapter."""
        # Stub logic for serialization
        data = {
            "connector_id": connector.connector_id,
            "lifecycle_state": connector.lifecycle_state.value,
        }
        return self._adapter.write_connector_record(connector.connector_id, data)

    def get_connector(self, connector_id: str) -> Optional[Connector]:
        """Translates a dict from adapter to a domain Connector."""
        # Stub
        _logger.debug(f"Stub get_connector for {connector_id}")
        return None

    def load_all_connectors(self) -> List[Connector]:
        """Loads all and builds aggregates."""
        records = self._adapter.fetch_all_connectors()
        connectors = []
        for record in records:
            import json
            from ...domain.models import ConnectorLifecycleState, ConnectorManifest
            
            try:
                state = ConnectorLifecycleState(record.get('lifecycle_state', 'registered').lower())
            except ValueError:
                state = ConnectorLifecycleState.REGISTERED
                
            manifest_json = record.get('manifest_json', '{}')
            try:
                manifest_dict = json.loads(manifest_json)
                manifest = ConnectorManifest(**manifest_dict)
            except Exception:
                # Basic fallback
                manifest = ConnectorManifest(
                    connector_id=record['connector_id'],
                    connector_type_id=record.get('connector_type_id', 'mock'),
                    display_name=record.get('display_name', record['connector_id']),
                    capabilities=[]
                )
                
            connector = Connector(
                manifest=manifest,
                lifecycle_state=state
            )
            connectors.append(connector)
        return connectors

    def save_manifest(self, manifest: ConnectorManifest) -> bool:
        """Saves only the manifest part."""
        # Stub
        return True

    def delete_connector(self, connector_id: str) -> bool:
        return self._adapter.delete_connector_record(connector_id)
