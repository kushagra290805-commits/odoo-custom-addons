from typing import Dict, Optional
from odoo.addons.nexora_studio.services.adapters.component_adapter import ComponentAdapter

class AdapterRegistry:
    """
    Extensible registry for ComponentAdapters. Future adapters can be registered
    without modifying this core registry.
    """
    def __init__(self):
        self._adapters: Dict[str, ComponentAdapter] = {}
        
    def register(self, adapter: ComponentAdapter) -> None:
        if adapter.source_ecosystem in self._adapters:
            raise ValueError(f"Adapter for {adapter.source_ecosystem} already registered.")
        self._adapters[adapter.source_ecosystem] = adapter
        
    def get_adapter(self, source_ecosystem: str) -> Optional[ComponentAdapter]:
        return self._adapters.get(source_ecosystem)
