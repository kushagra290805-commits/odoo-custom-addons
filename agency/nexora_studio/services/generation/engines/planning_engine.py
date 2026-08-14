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

            # Execute the plan using PlanOrchestrator
            from odoo.addons.nexora_studio.services.planning.orchestrator import PlanOrchestrator
            from odoo.addons.nexora_studio.services.capabilities.selection_engine import CapabilitySelectionEngine
            from odoo.addons.nexora_studio.services.capabilities.resolver import CapabilityResolver
            from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
            from odoo.addons.nexora_studio.services.capabilities.router import UniversalCapabilityRouter
            from odoo.addons.nexora_studio.services.capabilities.policy import CapabilityPolicyEngine
            from odoo.addons.nexora_studio.services.capabilities.security import SecurityLayer
            from odoo.addons.nexora_studio.services.capabilities.middleware import MiddlewarePipeline
            from odoo.addons.nexora_studio.services.capabilities.scheduler import ExecutionScheduler
            from odoo.addons.nexora_studio.services.capabilities.strategy import ExecutionStrategy
            from odoo.addons.nexora_studio.services.capabilities.executors.local import LocalToolExecutor
            from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType

            env = runtime.orchestrator.env if hasattr(runtime, 'orchestrator') else None
            repo = CapabilityRepository(env)
            resolver = CapabilityResolver(repo)

            class ToolRegistryWrapper:
                def __init__(self, e): self.env = e
                def resolve_tool(self, tool_id): return None

            tool_registry = ToolRegistryWrapper(env)
            executors = {ExecutionTargetType.LOCAL: LocalToolExecutor(tool_registry)}

            router = UniversalCapabilityRouter(resolver, CapabilityPolicyEngine(), SecurityLayer(), MiddlewarePipeline(), ExecutionScheduler(ExecutionStrategy()), executors)
            cse = CapabilitySelectionEngine(resolver, router)
            orchestrator = PlanOrchestrator(cse)

            trace = orchestrator.execute_plan(plan)

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

        import dataclasses
        # Store modular_blueprint in artifact.generation_metadata for downstream Phase B engines
        new_generation_metadata = dict(artifact.generation_metadata)
        new_generation_metadata["modular_blueprint"] = dataclasses.asdict(modular_blueprint) if dataclasses.is_dataclass(modular_blueprint) else {}

        # VERY IMPORTANT: Downstream legacy engines have been migrated!
        # We no longer need to generate a mapped legacy blueprint.

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(generation_metadata=new_generation_metadata),
            metadata=metadata,
            error=None
        )
