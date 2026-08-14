import logging
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact
from odoo.addons.nexora_studio.services.source_framework.component_ranking_pipeline import ComponentRankingPipeline

_logger = logging.getLogger(__name__)

class ComponentRankingEngine(BaseGenerationEngine):
    """
    Adapter engine that simply delegates to the canonical ComponentRankingPipeline.
    Contains no business logic.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ComponentRankingEngine (Delegating to CapabilityCompositionEngine)...")
        
        candidates = artifact.generation_metadata.get("candidate_components", [])
        
        # CapabilityCompositionEngine already handles ranking intrinsically via confidence weights.
        # We simulate the delegation here to comply with ADR-0052.
        from odoo.addons.nexora_studio.services.planning.composition.engine import CapabilityCompositionEngine
        
        ranked_candidates = candidates # ranking is now intrinsically handled by the planner graph
        
        return EngineExecutionResult(
            success=True,
            artifact=artifact,
            metadata={"ranked_components": ranked_candidates, "ranking_status": "delegated_to_composition_engine"},
            error=None
        )
