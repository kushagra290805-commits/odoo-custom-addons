from typing import List
from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeChunk

class ContextBudgetManager:
    """
    Prevents token blowout during RAG context assembly.
    """
    def assemble_context(self, chunks: List[KnowledgeChunk], token_budget: int) -> List[KnowledgeChunk]:
        """
        Deduplicates, ranks, and strictly trims chunks to fit the budget.
        """
        # 1. Deduplicate based on unique knowledge_id
        unique_chunks = {chunk.descriptor.knowledge_id: chunk for chunk in chunks}
        
        # 2. Sort by confidence (descending)
        sorted_chunks = sorted(unique_chunks.values(), key=lambda c: c.descriptor.confidence, reverse=True)
        
        # 3. Budget limits
        assembled = []
        current_tokens = 0
        
        for chunk in sorted_chunks:
            # Naive token estimation for architecture foundation (chars / 4)
            estimated_tokens = len(chunk.content) // 4
            
            if current_tokens + estimated_tokens > token_budget:
                break
                
            assembled.append(chunk)
            current_tokens += estimated_tokens
            
        return assembled
