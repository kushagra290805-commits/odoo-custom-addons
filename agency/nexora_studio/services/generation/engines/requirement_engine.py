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

        existing = artifact.requirements
        # Phase 47.18 (Part A): carry brief-extracted business identity into
        # the canonical RequirementModel and branding so downstream research
        # queries and generation prompts use the actual client facts.
        business_name = raw_req.preferences.get("business_name", "")
        business_category = raw_req.preferences.get("business_category", "")
        location = raw_req.preferences.get("location", "")
        services = list(raw_req.preferences.get("services", []))

        branding = dict(existing.branding)
        if business_name:
            branding.setdefault('business_name', business_name)
        if business_category:
            branding.setdefault('business_category', business_category)
        if location:
            branding.setdefault('location', location)
        if services:
            branding.setdefault('services', services)

        from odoo.addons.nexora_studio.services.design.capability_policy import (
            infer_capabilities, backend_required
        )

        capabilities = infer_capabilities(
            business_category=business_category,
            services=services,
            features=list(raw_req.preferences.get("features", [])),
            goals=list(raw_req.preferences.get("goals", [])),
            raw_input=existing.raw_input or raw_req.intent,
        )

        model = RequirementModel(
            raw_input=existing.raw_input or raw_req.intent,
            domain=existing.domain or domain,
            target_audience=existing.target_audience or audience,
            business_name=existing.business_name or business_name,
            business_category=existing.business_category or business_category,
            location=existing.location or location,
            goals=list(existing.goals) or list(raw_req.preferences.get("goals", [])),
            features=list(existing.features) or list(raw_req.preferences.get("features", [])),
            branding=branding,
            seo=dict(existing.seo),
            accessibility=dict(existing.accessibility),
            mobile_expected=bool(existing.mobile_expected
                                 or raw_req.preferences.get("mobile_expected")),
            capabilities=capabilities,
            backend_required=backend_required(capabilities),
        )
        
        # Also store raw_req in metadata temporarily for next engines
        metadata = {"raw_requirement": raw_req.__dict__}
        
        return EngineExecutionResult(success=True, artifact=artifact.evolve(requirements=model), metadata=metadata, error=None)
