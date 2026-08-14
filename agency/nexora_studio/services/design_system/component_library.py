from typing import Dict, List, Optional
from odoo.addons.nexora_studio.services.design_system.component_schema import ComponentSchema
import logging

_logger = logging.getLogger(__name__)

class ComponentLibrary:
    """
    Registry of all approved, reusable building blocks for the Spatial Platform.
    Adopts an Atomic Design-inspired hierarchy.
    """
    def __init__(self):
        self._schemas: Dict[str, ComponentSchema] = {}
        
    def register_component(self, schema: ComponentSchema) -> None:
        if schema.component_id in self._schemas:
            _logger.warning(f"Overwriting component schema: {schema.component_id}")
        self._schemas[schema.component_id] = schema
        _logger.debug(f"Registered {schema.category} Component: {schema.component_id} v{schema.version}")
        
    def get_component(self, component_id: str) -> Optional[ComponentSchema]:
        return self._schemas.get(component_id)
        
    def get_all_components(self) -> List[ComponentSchema]:
        return list(self._schemas.values())
        
    def get_components_by_category(self, category: str) -> List[ComponentSchema]:
        return [s for s in self._schemas.values() if s.category.lower() == category.lower()]
        
    def search_by_capability(self, capability: str) -> List[ComponentSchema]:
        """Allows AI to semantically retrieve components that fulfill a specific capability."""
        return [s for s in self._schemas.values() if capability in s.capabilities]
