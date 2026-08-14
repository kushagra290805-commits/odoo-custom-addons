import logging
from typing import Dict, List, Optional, Tuple

from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_provider import KnowledgeProvider
from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeDescriptor
from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_event_bus import KnowledgeEventBus

_logger = logging.getLogger(__name__)

class KnowledgeRegistry:
    """
    Manages active KnowledgeProviders and maintains a fast O(1) cache of descriptors.
    """
    def __init__(self, event_bus: KnowledgeEventBus):
        self._providers: Dict[str, KnowledgeProvider] = {}
        self._descriptor_cache: Dict[str, Tuple[KnowledgeProvider, KnowledgeDescriptor]] = {}
        self._event_bus = event_bus
        
    def register_provider(self, provider: KnowledgeProvider) -> None:
        try:
            provider.initialize()
            self._providers[provider.provider_id] = provider
            self._rebuild_cache()
            _logger.info(f"Registered KnowledgeProvider: {provider.provider_id}")
            self._event_bus.publish("ProviderRegistered", {"provider_id": provider.provider_id})
        except Exception as e:
            _logger.error(f"Failed to register knowledge provider {provider.provider_id}: {e}")
            
    def unregister_provider(self, provider_id: str) -> None:
        if provider_id in self._providers:
            provider = self._providers[provider_id]
            provider.shutdown()
            del self._providers[provider_id]
            self._rebuild_cache()
            self._event_bus.publish("ProviderUnregistered", {"provider_id": provider_id})
            
    def get_providers(self) -> List[KnowledgeProvider]:
        return list(self._providers.values())
            
    def _rebuild_cache(self) -> None:
        self._descriptor_cache.clear()
        for provider_id, provider in self._providers.items():
            if provider.health().get("status") == "healthy":
                for desc in provider.metadata():
                    # Format: {provider_id}/{knowledge_id} to prevent cross-provider collisions
                    composite_id = f"{provider.provider_id}/{desc.knowledge_id}"
                    self._descriptor_cache[composite_id] = (provider, desc)

    def resolve_descriptor(self, composite_id: str) -> Optional[Tuple[KnowledgeProvider, KnowledgeDescriptor]]:
        """O(1) lookup for a descriptor."""
        return self._descriptor_cache.get(composite_id)
