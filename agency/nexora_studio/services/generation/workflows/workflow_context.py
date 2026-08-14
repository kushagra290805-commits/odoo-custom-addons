from typing import List, Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.tool_capability import ToolCapability
from odoo.addons.nexora_studio.services.providers.provider_registry import ProviderRegistry
from odoo.addons.nexora_studio.services.adapters.adapter_registry import AdapterRegistry

class WorkflowContext:
    """
    State container passed through the workflow stages. Exposes available ToolCapabilities.
    """
    def __init__(self, provider_registry: ProviderRegistry, adapter_registry: AdapterRegistry):
        self.provider_registry = provider_registry
        self.adapter_registry = adapter_registry
        self.capabilities: List[ToolCapability] = []
        self.state: Dict[str, Any] = {}
        
    def register_capability(self, capability: ToolCapability) -> None:
        self.capabilities.append(capability)
        
    def get_capabilities(self) -> List[ToolCapability]:
        return self.capabilities
