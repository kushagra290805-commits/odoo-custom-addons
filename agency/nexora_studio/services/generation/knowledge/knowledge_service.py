from typing import List
import logging

from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeQuery, KnowledgeChunk
from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_registry import KnowledgeRegistry
from odoo.addons.nexora_studio.services.generation.knowledge.semantic_retrieval import SemanticRetrievalEngine
from odoo.addons.nexora_studio.services.generation.knowledge.context_budget_manager import ContextBudgetManager
from odoo.addons.nexora_studio.services.generation.knowledge.enums import RetrievalStrategy

_logger = logging.getLogger(__name__)

class KnowledgeService:
    """
    The orchestrator. Routes queries between semantic engines and providers,
    assembles context, and applies token budgets.
    """
    def __init__(self, registry: KnowledgeRegistry, retrieval_engine: SemanticRetrievalEngine, budget_manager: ContextBudgetManager):
        self._registry = registry
        self._retrieval = retrieval_engine
        self._budget = budget_manager
        
    def query(self, query: KnowledgeQuery) -> List[KnowledgeChunk]:
        raw_chunks = []
        
        # 1. Provider (Exact/Keyword) Retrieval
        if query.retrieval_strategy in [RetrievalStrategy.EXACT, RetrievalStrategy.KEYWORD, RetrievalStrategy.HYBRID]:
            for provider in self._registry.get_providers():
                try:
                    chunks = provider.fetch(query)
                    raw_chunks.extend(chunks)
                except Exception as e:
                    _logger.warning(f"Provider {provider.provider_id} fetch failed: {e}")
                    
        # 2. Semantic Retrieval
        if query.retrieval_strategy in [RetrievalStrategy.SEMANTIC, RetrievalStrategy.HYBRID]:
            embeddings = self._retrieval.retrieve(query)
            # In real system, we'd hydrate the full chunk text from Odoo here using the ID
            # For this foundation, we just acknowledge the flow.
            
        # 3. Context Budgeting & Deduplication
        assembled_context = self._budget.assemble_context(raw_chunks, query.token_budget)
        return assembled_context
