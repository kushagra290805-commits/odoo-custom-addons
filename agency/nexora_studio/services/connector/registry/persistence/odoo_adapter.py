"""
Odoo Connector Persistence Adapter
==================================
Part 3 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Any, Dict, List, Optional
import threading
import time
import psycopg2

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
        # Store the dbname so we can open new cursors for background threads
        self._dbname = env.cr.dbname if env and getattr(env, 'cr', None) else None

    def read_connector_record(self, connector_id: str) -> Optional[Dict[str, Any]]:
        if self._env is None:
            return None
        # Reading is generally safe, but if we're in a background thread without a cursor, we need one.
        import odoo
        current_thread = threading.current_thread()
        has_active_env = getattr(current_thread, 'testing', False) or bool(getattr(odoo.api.Environment, 'envs', {}))
        needs_new_cursor = not has_active_env or (hasattr(self._env, 'cr') and self._env.cr.closed)
        
        if needs_new_cursor and self._dbname:
            from odoo.modules.registry import Registry
            from odoo import api, SUPERUSER_ID
            reg = Registry(self._dbname)
            with reg.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                record = env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
                if not record:
                    return None
                return self._record_to_dict(record)
        else:
            record = self._env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
            if not record:
                return None
            return self._record_to_dict(record)

    def write_connector_record(self, connector_id: str, data: Dict[str, Any], is_full_write: bool = True) -> bool:
        """
        Performs a full or partial update/create.
        Now routes through the safe background execution mechanism.
        """
        return self._execute_safe_write(connector_id, data, is_full_write=is_full_write)
        
    def _execute_safe_write(self, connector_id: str, data: Dict[str, Any], is_full_write: bool = False) -> bool:
        """
        Executes a write operation with bounded retries for SerializationFailures.
        Automatically uses a dedicated cursor if running in a background thread or if the current cursor is closed.
        """
        if self._env is None or not self._dbname:
            return False

        # Determine if we need a new cursor (background thread or closed cursor)
        import odoo
        current_thread = threading.current_thread()
        has_active_env = getattr(current_thread, 'testing', False) or bool(getattr(odoo.api.Environment, 'envs', {}))
        
        needs_new_cursor = not has_active_env or (hasattr(self._env, 'cr') and self._env.cr.closed)
        
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(1, max_retries + 1):
            if needs_new_cursor:
                from odoo.modules.registry import Registry
                from odoo import api, SUPERUSER_ID
                reg = Registry(self._dbname)
                try:
                    with reg.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        success = self._do_write(env, connector_id, data, is_full_write)
                        if success:
                            cr.commit()
                        else:
                            cr.rollback()
                        return success
                except psycopg2.errors.SerializationFailure as e:
                    _logger.warning(f"SerializationFailure on background write for '{connector_id}' (attempt {attempt}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                except Exception as e:
                    _logger.error(f"Failed safe background write for '{connector_id}': {e}")
                    return False
            else:
                # Use existing environment, but we must catch serialization errors
                try:
                    # In an existing transaction, a SerializationFailure will ruin the transaction.
                    # We can use a savepoint to isolate this write.
                    with self._env.cr.savepoint():
                        return self._do_write(self._env, connector_id, data, is_full_write)
                except psycopg2.errors.SerializationFailure as e:
                    _logger.warning(f"SerializationFailure on savepoint write for '{connector_id}' (attempt {attempt}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                except Exception as e:
                    _logger.error(f"Failed safe write for '{connector_id}': {e}")
                    return False
                    
        _logger.error(f"Max retries ({max_retries}) exhausted for connector '{connector_id}' persistence.")
        return False

    def _do_write(self, env: Any, connector_id: str, data: Dict[str, Any], is_full_write: bool) -> bool:
        record = env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)

        # Phase 44.2 (W5 / G-20): callers may use either 'lifecycle_state'
        # (canonical) or legacy 'state'; normalize to the canonical key.
        lifecycle_state = data.get('lifecycle_state', data.get('state'))

        vals = {}

        if is_full_write:
            # Full write populates all mapped fields, falling back to defaults if missing
            vals = {
                'name': data.get('display_name', connector_id),
                'description': data.get('description', ''),
                'author': data.get('author', ''),
                'homepage_url': data.get('homepage_url', ''),
                'documentation_url': data.get('documentation_url', ''),
                'state': (lifecycle_state or 'registered').lower(),
            }
            # Phase 44.2 (W4 / G-03): a full write must NEVER clobber a
            # populated manifest_json with '{}' when the caller did not provide
            # one. Preserve the existing value on update.
            if 'manifest_json' in data:
                vals['manifest_json'] = data['manifest_json']
            elif record and record.manifest_json and record.manifest_json != '{}':
                vals['manifest_json'] = record.manifest_json
            else:
                vals['manifest_json'] = '{}'
            if 'health_status' in data:
                vals['health_status'] = data['health_status']
        else:
            # Partial update only includes fields provided in data
            if 'display_name' in data: vals['name'] = data['display_name']
            if 'description' in data: vals['description'] = data['description']
            if 'author' in data: vals['author'] = data['author']
            if 'homepage_url' in data: vals['homepage_url'] = data['homepage_url']
            if 'documentation_url' in data: vals['documentation_url'] = data['documentation_url']
            if lifecycle_state is not None: vals['state'] = lifecycle_state.lower()
            if 'health_status' in data: vals['health_status'] = data['health_status']
            if 'manifest_json' in data: vals['manifest_json'] = data['manifest_json']

        ctype_id = data.get('connector_type_id')
        if ctype_id:
            ctype_record = env['nexora.connector_type'].search([('type_code', '=', ctype_id)], limit=1)
            if ctype_record:
                vals['connector_type_id'] = ctype_record.id

        if not record:
            vals['connector_id'] = connector_id
            env['nexora.connector'].create(vals)
        else:
            record.write(vals)
            
        return True

    def fetch_all_connectors(self) -> List[Dict[str, Any]]:
        if self._env is None:
            return []
        import odoo
        current_thread = threading.current_thread()
        has_active_env = getattr(current_thread, 'testing', False) or bool(getattr(odoo.api.Environment, 'envs', {}))
        needs_new_cursor = not has_active_env or (hasattr(self._env, 'cr') and self._env.cr.closed)
        
        if needs_new_cursor and self._dbname:
            from odoo.modules.registry import Registry
            from odoo import api, SUPERUSER_ID
            reg = Registry(self._dbname)
            with reg.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                records = env['nexora.connector'].search([])
                return [self._record_to_dict(rec) for rec in records]
        else:
            records = self._env['nexora.connector'].search([])
            return [self._record_to_dict(rec) for rec in records]

    def delete_connector_record(self, connector_id: str) -> bool:
        if self._env is None:
            return False
        import odoo
        current_thread = threading.current_thread()
        has_active_env = getattr(current_thread, 'testing', False) or bool(getattr(odoo.api.Environment, 'envs', {}))
        needs_new_cursor = not has_active_env or (hasattr(self._env, 'cr') and self._env.cr.closed)
        
        if needs_new_cursor and self._dbname:
            from odoo.modules.registry import Registry
            from odoo import api, SUPERUSER_ID
            reg = Registry(self._dbname)
            try:
                with reg.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    record = env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
                    if record:
                        record.unlink()
                        cr.commit()
                return True
            except Exception as e:
                _logger.error(f"Failed to delete connector record: {e}")
                return False
        else:
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
            'health_status': getattr(record, 'health_status', 'unknown'),
            'manifest_json': record.manifest_json or '{}',
        }
