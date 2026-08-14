"""
Odoo Connector Persistence Adapter
==================================
Part 3 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Any, Dict, List, Optional

from .adapter import ConnectorPersistenceAdapter

_logger = get_logger(__name__)


class OdooConnectorPersistenceAdapter(ConnectorPersistenceAdapter):
    """
    Odoo-specific implementation of the ConnectorPersistenceAdapter.
    This is the ONLY class in the connector runtime that interacts with the Odoo ORM.
    """

    def __init__(self, env: Any):
        """
        Args:
            env: Odoo environment (`odoo.api.Environment`).
        """
        self._env = env

    def read_connector_record(self, connector_id: str) -> Optional[Dict[str, Any]]:
        if self._env is None:
            return None
        record = self._env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
        if not record:
            return None
        return self._record_to_dict(record)

    def write_connector_record(self, connector_id: str, data: Dict[str, Any]) -> bool:
        if self._env is None:
            return False
        record = self._env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
        
        # Prepare write values
        vals = {
            'name': data.get('display_name', connector_id),
            'description': data.get('description', ''),
            'author': data.get('author', ''),
            'homepage_url': data.get('homepage_url', ''),
            'documentation_url': data.get('documentation_url', ''),
            'state': data.get('lifecycle_state', 'registered').lower(),
            'manifest_json': data.get('manifest_json', '{}'),
        }
        
        # We need to resolve connector_type_id to an Odoo ID, but for now we assume it's created or we skip it if it's complex.
        # Actually, in Odoo it's a Many2one. If data provides the raw string `connector_type_id`, we'd look it up.
        ctype_id = data.get('connector_type_id')
        if ctype_id:
            ctype_record = self._env['nexora.connector_type'].search([('type_code', '=', ctype_id)], limit=1)
            if ctype_record:
                vals['connector_type_id'] = ctype_record.id

        if not record:
            vals['connector_id'] = connector_id
            try:
                self._env['nexora.connector'].create(vals)
                return True
            except Exception as e:
                _logger.error(f"Failed to create connector record: {e}")
                return False
        else:
            try:
                record.write(vals)
                return True
            except Exception as e:
                _logger.error(f"Failed to update connector record: {e}")
                return False

    def fetch_all_connectors(self) -> List[Dict[str, Any]]:
        if self._env is None:
            return []
        records = self._env['nexora.connector'].search([])
        return [self._record_to_dict(rec) for rec in records]

    def delete_connector_record(self, connector_id: str) -> bool:
        if self._env is None:
            return False
        record = self._env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
        if record:
            try:
                record.unlink()
                return True
            except Exception as e:
                _logger.error(f"Failed to delete connector record: {e}")
                return False
        return True

    def _record_to_dict(self, record: Any) -> Dict[str, Any]:
        """Convert Odoo recordset to primitive dict for the platform layer."""
        return {
            'connector_id': record.connector_id,
            'display_name': record.name,
            'connector_type_id': record.connector_type_id.type_code if record.connector_type_id else 'mock',
            'description': record.description or '',
            'author': record.author or '',
            'homepage_url': record.homepage_url or '',
            'documentation_url': record.documentation_url or '',
            'lifecycle_state': record.state,
            'manifest_json': record.manifest_json or '{}',
        }
