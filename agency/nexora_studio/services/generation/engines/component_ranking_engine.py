import logging
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class ComponentRankingEngine(BaseGenerationEngine):
    """
    Adapter engine that simply delegates to the canonical ComponentRankingPipeline.
    Contains no business logic.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ComponentRankingEngine (Delegating to CapabilityCompositionEngine)...")
        
        candidates = artifact.generation_metadata.get("candidate_components", [])
        
        # SearchEngine already applied the sole ComponentRankingPipeline
        # decision. This state preserves that ranked envelope unchanged.
        return EngineExecutionResult(
            success=True,
            artifact=artifact,
            metadata={
                "ranked_components": candidates,
                "ranking_status": "ranked_by_search_engine",
            },
            error=None
        )
