import logging
from typing import List

from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_registry import KnowledgeRegistry
from odoo.addons.nexora_studio.services.generation.knowledge.embedding_manager import EmbeddingManager
from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_event_bus import KnowledgeEventBus
from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeChunk

_logger = logging.getLogger(__name__)

class KnowledgeLifecycleManager:
    """
    Orchestrates the lifecycle of design knowledge, sync schedules, and triggers embeddings.
    """
    def __init__(self, registry: KnowledgeRegistry, embedding_manager: EmbeddingManager, event_bus: KnowledgeEventBus):
        self._registry = registry
        self._embedding_manager = embedding_manager
        self._event_bus = event_bus
        
    def trigger_ingestion(self, provider_id: str) -> None:
        """Trigger a sync for a specific provider."""
        _logger.info(f"Triggering ingestion for provider {provider_id}")
        
        # 1. Fetch chunks (in reality, via cron background job to avoid blocking)
        # Mock logic for architecture demonstration
        chunks_to_embed = []
        
        if chunks_to_embed:
            # 2. Generate and store embeddings
            success = self._embedding_manager.embed_and_store(chunks_to_embed)
            if success:
                self._event_bus.publish("EmbeddingsGenerated", {"provider_id": provider_id, "count": len(chunks_to_embed)})
            else:
                self._event_bus.publish("EmbeddingsInvalidated", {"provider_id": provider_id})
                
    def handle_record_deleted(self, knowledge_id: str) -> None:
        """Called when Odoo unlinks a record."""
        # 1. Instruct store to delete vector
        self._embedding_manager._store.delete(knowledge_id)
        # 2. Trigger cache rebuild on registry
        self._registry._rebuild_cache()
        # 3. Publish
        self._event_bus.publish("KnowledgeDeleted", {"knowledge_id": knowledge_id})
