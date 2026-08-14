from typing import Dict, Optional
from odoo.addons.nexora_studio.services.providers.provider_interface import ProviderInterface

class ProviderRegistry:
    """
    Central registry for managing Provider lifecycles via Dependency Injection.
    """
    def __init__(self, lifecycle_manager=None):
        self._providers: Dict[str, ProviderInterface] = {}
        self.lifecycle_manager = lifecycle_manager
        
    def register(self, provider_id: str, provider: ProviderInterface) -> None:
        if provider_id in self._providers:
            raise ValueError(f"Provider {provider_id} already registered.")
        
        provider.initialize()
        self._providers[provider_id] = provider
        
        # Publish capabilities to the UCEL lifecycle manager
        if self.lifecycle_manager and hasattr(provider, 'get_capabilities'):
            capabilities = provider.get_capabilities()
            for cap in capabilities:
                # Assuming cap is a CapabilityManifest or can be converted to one
                # Provider models would be updated to emit CapabilityManifests directly.
                self.lifecycle_manager.register(cap)
        
    def get_provider(self, provider_id: str) -> Optional[ProviderInterface]:
        return self._providers.get(provider_id)
        
    def shutdown_all(self) -> None:
        for provider in self._providers.values():
            provider.shutdown()
