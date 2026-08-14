from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from odoo.addons.nexora_studio.services.generation.knowledge.enums import (
    KnowledgeCategory, RetrievalStrategy, KnowledgeDomain
)

@dataclass(frozen=True)
class KnowledgeQuery:
    """Structured query object for retrieving knowledge."""
    text: str
    domain: Optional[KnowledgeDomain] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    project: Optional[str] = None
    client: Optional[str] = None
    language: str = "en-US"
    token_budget: int = 1000
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID

@dataclass(frozen=True)
class KnowledgeDescriptor:
    """Lightweight metadata manifest for a specific piece of design intelligence."""
    knowledge_id: str
    provider_id: str
    category: KnowledgeCategory
    tags: List[str]
    version: str
    language: str
    confidence: float
    updated_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class KnowledgeChunk:
    """The actual retrievable content object."""
    descriptor: KnowledgeDescriptor
    content: str
    
@dataclass(frozen=True)
class KnowledgeEmbedding:
    """Vector representation of a chunk."""
    knowledge_id: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
