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
        
        combined_intent = artifact.requirements.raw_input
        if artifact.requirements.current_supervisor_instruction:
            combined_intent += f"\n\n[Supervisor Instruction]: {artifact.requirements.current_supervisor_instruction}"
            
        raw_req = analyzer.analyze(combined_intent)
        
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
        positioning = raw_req.preferences.get("positioning", "")
        differentiators = raw_req.preferences.get("differentiators", "")
        visual = raw_req.preferences.get("visual", "")
        cta = raw_req.preferences.get("cta", "")

        branding = dict(existing.branding)
        if business_name:
            branding.setdefault('business_name', business_name)
        if business_category:
            branding.setdefault('business_category', business_category)
        if location:
            branding.setdefault('location', location)
        if services:
            branding.setdefault('services', services)
        if positioning:
            branding.setdefault('positioning', positioning)
        if differentiators:
            branding.setdefault('differentiators', differentiators)
        if visual:
            # Phase 47.40: bounded brand/style signal for the ThemeEngine
            # visual-direction policy (labeled brief line only).
            branding.setdefault('visual', visual)
        if cta:
            branding.setdefault('cta', cta)

        from odoo.addons.nexora_studio.services.design.capability_policy import (
            infer_capabilities, backend_required
        )

        capabilities = infer_capabilities(
            business_category=business_category,
            services=services,
            features=list(raw_req.preferences.get("features", [])),
            goals=list(raw_req.preferences.get("goals", [])),
            raw_input=combined_intent,
        )

        model = RequirementModel(
            raw_input=existing.raw_input, # Always strictly immutable original intent
            current_supervisor_instruction=existing.current_supervisor_instruction,
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
