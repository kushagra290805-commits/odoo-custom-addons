from abc import ABC, abstractmethod
from typing import Dict, Any
from odoo.addons.nexora_studio.services.design_system.component_schema import ComponentSchema

class ComponentAdapter(ABC):
    """
    Base interface for converting external UI code/components into 
    the canonical ComponentSchema format.
    """
    @abstractmethod
    def parse_component(self, raw_data: Any) -> ComponentSchema:
        """Parses raw provider data and returns a normalized schema."""
        pass
        
    @property
    @abstractmethod
    def source_ecosystem(self) -> str:
        """e.g. 'shadcn', 'penpot', 'magic_ui'"""
        pass
