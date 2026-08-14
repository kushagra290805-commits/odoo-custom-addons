import logging
import json
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, RequirementModel

_logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ["SaaS", "Ecommerce", "Portfolio", "Agency", "Real Estate", "Healthcare", "Education", "Restaurant"]

class RequirementEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing RequirementEngine (Delegating to RequirementAnalyzer)...")
        from odoo.addons.nexora_studio.services.design.requirement_analyzer import RequirementAnalyzer
        
        analyzer = RequirementAnalyzer()
        raw_req = analyzer.analyze(artifact.requirements.raw_input)
        
        # We temporarily map the RawRequirement (new) back into RequirementModel (legacy)
        # to preserve downstream compatibility until they are fully migrated to blueprint models.
        # Actually, RawRequirement just has intent, constraints, and preferences.
        # We will attempt to use AI as originally done but via the new paradigm if needed.
        # However, the instruction states "replace only their internal implementation, delegate to new intelligence modules".
        
        domain = raw_req.preferences.get("domain", "Agency")
        audience = raw_req.preferences.get("target_audience", "General Public")
        
        model = RequirementModel(
            raw_input=raw_req.intent,
            domain=domain,
            target_audience=audience,
            goals=[],
            features=raw_req.preferences.get("features", []),
            branding={},
            seo={},
            accessibility={}
        )
        
        # Also store raw_req in metadata temporarily for next engines
        metadata = {"raw_requirement": raw_req.__dict__}
        
        return EngineExecutionResult(success=True, artifact=artifact.evolve(requirements=model), metadata=metadata, error=None)
