import logging
from typing import Dict, Any

from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_registry import KnowledgeRegistry
from odoo.addons.nexora_studio.services.generation.knowledge.embedding_store import EmbeddingStore

_logger = logging.getLogger(__name__)

class KnowledgeHealthService:
    """
    Monitors the health of the entire Knowledge Framework.
    """
    def __init__(self, registry: KnowledgeRegistry, store: EmbeddingStore):
        self._registry = registry
        self._store = store
        
    def system_status(self) -> Dict[str, Any]:
        """Produce a diagnostic readout for Console/Admin dashboards."""
        status = {
            "providers": {},
            "registry": {
                "active_descriptors": len(self._registry._descriptor_cache)
            },
            "vector_store": {
                "online": True, # In a real implementation, ping the DB
            }
        }
        
        for provider in self._registry.get_providers():
            status["providers"][provider.provider_id] = provider.health()
            
        return status
