from typing import List, Any
import logging

from odoo.addons.nexora_studio.services.generation.knowledge.embedding_store import EmbeddingStore
from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeQuery, KnowledgeEmbedding

_logger = logging.getLogger(__name__)

class SemanticRetrievalEngine:
    """
    Performs purely retrieval operations against the Vector DB.
    Does NOT do context assembly or budgeting.
    """
    def __init__(self, ai_provider_manager: Any, store: EmbeddingStore):
        self._ai = ai_provider_manager
        self._store = store
        
    def retrieve(self, query: KnowledgeQuery) -> List[KnowledgeEmbedding]:
        try:
            # 1. Embed query string
            query_vector = self._ai.generate_embedding(query.text)
            
            # 2. Query Store
            limit = 20 # Arbitrary high limit, budgeting happens later
            results = self._store.search(query_vector, limit, query.filters)
            return results
        except Exception as e:
            _logger.exception(f"Semantic retrieval failed: {e}")
            return []
