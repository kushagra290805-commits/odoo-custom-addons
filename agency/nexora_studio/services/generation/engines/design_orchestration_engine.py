import logging
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class DesignOrchestrationEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing DesignOrchestrationEngine (Delegating to DesignIntelligenceEngine)...")
        # In Phase B, the modular blueprint is created upstream by PlanningEngine 
        # and stored in generation_metadata.
        modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint", {})
        
        try:
            # Since PlanOrchestrator handles actual provider routing in the new architecture,
            # this engine just solidifies the design blueprint.
            _logger.info("DesignOrchestrationEngine completed successfully via upstream DesignIntelligenceEngine output.")
            return EngineExecutionResult(
                success=True,
                artifact=artifact.evolve(design={"status": "completed_via_design_intelligence", "blueprint": modular_blueprint_dict}),
                metadata={"design_orchestrator": "executed"},
                error=None
            )
        except Exception as e:
            _logger.error(f"DesignOrchestrationEngine failed: {str(e)}", exc_info=True)
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                error=f"Design orchestration failed: {str(e)}"
            )
