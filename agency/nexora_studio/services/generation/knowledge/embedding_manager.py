import logging
import typing
from typing import Any, List, Dict, Optional

from odoo.addons.nexora_studio.services.generation.knowledge.embedding_store import EmbeddingStore
from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeChunk, KnowledgeEmbedding

_logger = logging.getLogger(__name__)

class EmbeddingManager:
    """
    Responsible ONLY for mathematical conversion of Text -> Vector
    and pushing the result to the abstract EmbeddingStore.
    """
    def __init__(self, ai_provider_manager: Any, store: EmbeddingStore):
        self._ai = ai_provider_manager
        self._store = store
        
    def embed_and_store(self, chunks: List[KnowledgeChunk]) -> bool:
        try:
            embeddings_to_store = []
            for chunk in chunks:
                # Ask AI Provider Manager to generate vector
                vector = self._ai.generate_embedding(chunk.content)
                embeddings_to_store.append(
                    KnowledgeEmbedding(
                        knowledge_id=chunk.descriptor.knowledge_id,
                        vector=vector,
                        metadata=chunk.descriptor.metadata
                    )
                )
            
            if embeddings_to_store:
                return self._store.store(embeddings_to_store)
            return True
        except Exception as e:
            _logger.exception(f"Failed to generate or store embeddings: {e}")
            return False
