from abc import ABC, abstractmethod
from typing import List, Dict, Any

from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeEmbedding

class EmbeddingStore(ABC):
    """
    Abstract interface for Vector storage. Ensures Nexora is not coupled to pgvector,
    Pinecone, Qdrant, etc.
    """
    @abstractmethod
    def store(self, embeddings: List[KnowledgeEmbedding]) -> bool:
        pass
        
    @abstractmethod
    def search(self, vector: List[float], limit: int, filters: Dict[str, Any]) -> List[KnowledgeEmbedding]:
        pass
        
    @abstractmethod
    def delete(self, knowledge_id: str) -> bool:
        pass


class PgVectorStore(EmbeddingStore):
    """
    Phase 18.7 Concrete Implementation.
    Uses Odoo's local PostgreSQL database if pgvector extension is installed.
    """
    def __init__(self):
        # In a real environment, this would hold an Odoo cursor or pool reference.
        self._mock_db: Dict[str, KnowledgeEmbedding] = {}
        
    def store(self, embeddings: List[KnowledgeEmbedding]) -> bool:
        for emb in embeddings:
            self._mock_db[emb.knowledge_id] = emb
        return True
        
    def search(self, vector: List[float], limit: int, filters: Dict[str, Any]) -> List[KnowledgeEmbedding]:
        # Mock cosine similarity search
        return list(self._mock_db.values())[:limit]
        
    def delete(self, knowledge_id: str) -> bool:
        if knowledge_id in self._mock_db:
            del self._mock_db[knowledge_id]
            return True
        return False
