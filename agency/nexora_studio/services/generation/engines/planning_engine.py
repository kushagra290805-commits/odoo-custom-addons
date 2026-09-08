import logging
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact
from odoo.addons.nexora_studio.services.generation.engines.base_engine import EngineExecutionResult

_logger = logging.getLogger(__name__)

DOMAIN_TEMPLATES = {
    "SaaS": [{"path": "/", "name": "Home"}, {"path": "/pricing", "name": "Pricing"}, {"path": "/contact", "name": "Contact"}],
    "Ecommerce": [{"path": "/", "name": "Home"}, {"path": "/products", "name": "Products"}, {"path": "/cart", "name": "Cart"}, {"path": "/checkout", "name": "Checkout"}],
    "Portfolio": [{"path": "/", "name": "Home"}, {"path": "/about", "name": "About"}, {"path": "/projects", "name": "Projects"}],
    "Agency": [{"path": "/", "name": "Home"}, {"path": "/services", "name": "Services"}, {"path": "/contact", "name": "Contact"}],
    "Real Estate": [{"path": "/", "name": "Home"}, {"path": "/properties", "name": "Properties"}, {"path": "/agents", "name": "Agents"}],
    "Healthcare": [{"path": "/", "name": "Home"}, {"path": "/services", "name": "Services"}, {"path": "/doctors", "name": "Doctors"}, {"path": "/appointment", "name": "Book Appointment"}],
    "Education": [{"path": "/", "name": "Home"}, {"path": "/courses", "name": "Courses"}, {"path": "/admissions", "name": "Admissions"}],
    "Restaurant": [{"path": "/", "name": "Home"}, {"path": "/menu", "name": "Menu"}, {"path": "/reservations", "name": "Reservations"}],
}

class PlanningEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing PlanningEngine (Capability Planner)...")

        # The user instructed PlanningEngine -> IntelligentCapabilityPlanner
        from odoo.addons.nexora_studio.services.planning.planner import IntelligentCapabilityPlanner
        from odoo.addons.nexora_studio.services.planning.plan_optimizer import PlanOptimizer

        planner = IntelligentCapabilityPlanner()
        optimizer = PlanOptimizer()

        req = artifact.requirements
        objective = req.raw_input or f"Build a {req.domain} website"

        # We don't have the new modular blueprint yet (ThemeEngine will do that),
        # so we run the planner without it for now.
        try:
            plan = planner.plan(objective)
            plan = optimizer.optimize(plan)

            trace = runtime.orchestrator.execute_prepared_plan(plan)

            metadata = {
                "execution_plan": plan.graph.dict() if hasattr(plan.graph, 'dict') else {},
                "trace": {
                    "steps_completed": trace.steps_completed,
                    "steps_failed": trace.steps_failed
                }
            }
        except Exception as e:
            _logger.warning(f"PlanningEngine failed to generate capability plan: {e}")
            metadata = {}

        # Call DesignIntelligenceEngine to construct the canonical modular WebsiteBlueprint
        from odoo.addons.nexora_studio.services.design.engine import DesignIntelligenceEngine

        design_engine = DesignIntelligenceEngine()

        # DesignIntelligenceEngine generates the modular blueprint (Architecture, Layout, Style)
        modular_blueprint = design_engine.generate_blueprint(objective)

        # Inject canonical page-route hierarchy from DOMAIN_TEMPLATES into the modular blueprint.
        # DOMAIN_TEMPLATES is the single canonical source of URL page routes.
        # LayoutBlueprint.hierarchy carries URL paths that ArchitectureEngine normalises into
        # component_hierarchy entries with type="page". LayoutPlanner only sets layout strategy
        # and structural section names; we override hierarchy here with real URL routes so the
        # ArchitectureEngine and ContentEngine receive correct page paths (e.g. "/", "/pricing").
        domain = artifact.requirements.domain
        domain_pages = DOMAIN_TEMPLATES.get(domain, [{"path": "/", "name": "Home"}])
        modular_blueprint.layout.hierarchy = [p["path"] for p in domain_pages]

        if domain == "SaaS":
            modular_blueprint.layout.strategy = "Sidebar"

        # Phase 47.24 (ADR-0076): deterministic page-pattern selection. The
        # pattern is composition metadata (section sequence + reason),
        # selected from the domain/brief — no LLM call. ArchitectureEngine
        # derives page sections from it; the section builders themselves are
        # owned by CodeGenerationEngine.
        from odoo.addons.nexora_studio.services.design.page_patterns import select_pattern
        req = artifact.requirements
        brief_text = ' '.join(filter(None, [
            str(getattr(req, 'business_category', '') or ''),
            (req.branding or {}).get('business_category', ''),
            req.raw_input or '',
        ]))
        pattern = select_pattern(domain, brief_text)

        # Pattern semantics override the abstract component families so
        # ComponentIntelligenceEngine matches source-backed candidates
        # against the REAL section semantics the pages will render (same
        # override precedent as layout.hierarchy above).
        semantic_for = {
            'Hero': 'hero_section',
            'Content': 'content_section',
            'About': 'about_section',
            'ServicesGrid': 'services_grid',
            'FeatureGrid': 'feature_grid',
            'MenuHighlights': 'menu_highlights',
            'Pricing': 'pricing',
            'FAQ': 'faq',
            'Testimonial': 'testimonial_section',
            'ContactCTA': 'contact_cta',
            'Gallery': 'gallery',
        }
        pattern_semantics = list(dict.fromkeys(
            semantic_for.get(sec, sec.lower()) for sec in
            (pattern.get('home_sections') or []) + (pattern.get('secondary_sections') or [])
        ))
        if pattern_semantics:
            modular_blueprint.component.abstract_components = pattern_semantics

        import dataclasses
        # Store modular_blueprint in artifact.generation_metadata for downstream Phase B engines
        new_generation_metadata = dict(artifact.generation_metadata)
        new_generation_metadata["modular_blueprint"] = dataclasses.asdict(modular_blueprint) if dataclasses.is_dataclass(modular_blueprint) else {}
        # Phase 47.24: the selected pattern travels on the artifact for
        # ArchitectureEngine (sections) and AssetEngine (image intents).
        new_generation_metadata["page_pattern"] = {
            'id': pattern.get('id'),
            'reason': pattern.get('reason'),
            'home_sections': pattern.get('home_sections'),
            'secondary_sections': pattern.get('secondary_sections'),
        }

        # VERY IMPORTANT: Downstream legacy engines have been migrated!
        # We no longer need to generate a mapped legacy blueprint.

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(generation_metadata=new_generation_metadata),
            metadata=metadata,
            error=None
        )
