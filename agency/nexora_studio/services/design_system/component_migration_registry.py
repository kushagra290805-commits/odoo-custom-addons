from typing import Dict, Callable, Any, Optional
import logging

_logger = logging.getLogger(__name__)

class ComponentMigrationRegistry:
    """
    Handles schema evolution for components. When an old version of a component 
    needs to be loaded, this registry provides the migration strategies to 
    upgrade the data payload to the latest schema version.
    """
    def __init__(self):
        # Dict[component_id, Dict[from_version, migration_callable]]
        self._migrations: Dict[str, Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {}
        
    def register_migration(self, component_id: str, from_version: str, strategy: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        if component_id not in self._migrations:
            self._migrations[component_id] = {}
        self._migrations[component_id][from_version] = strategy
        _logger.debug(f"Registered migration for {component_id} from {from_version}")
        
    def migrate(self, component_id: str, from_version: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Attempts to upgrade a payload. If the exact version migration exists, applies it.
        """
        if component_id not in self._migrations:
            return payload # No migrations registered, assume it's valid
            
        strategy = self._migrations[component_id].get(from_version)
        if not strategy:
            _logger.warning(f"No migration strategy found for {component_id} from version {from_version}")
            return payload
            
        return strategy(payload)
