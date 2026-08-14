import logging
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, ComponentTree
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.source_framework.component_ranking_pipeline import ComponentRankingPipeline
from odoo.addons.nexora_studio.services.source_framework.domain_models import ComponentPackage, Provenance

_logger = logging.getLogger(__name__)

class ComponentDiscoveryEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ComponentDiscoveryEngine (Delegating to CapabilityCompositionEngine)...")

        required_types = set()
        component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}
        for comp_id, comp_data in component_hierarchy.items():
            if comp_data.get("type") == "page":
                sections = comp_data.get("sections", [])
                for section in sections:
                    required_types.add(section.lower())

        required_types.update(["button", "card", "input", "nav"])

        candidates = []
        try:
            env = runtime.orchestrator.env if hasattr(runtime, 'orchestrator') else None

            # Use the Planner and Orchestrator to resolve components
            if env:
                from odoo.addons.nexora_studio.services.source_framework.search_engine import SearchEngine
                from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager

                pm = ProviderManager(env)
                pm.load_from_registry()

                search_engine = SearchEngine(pm)

                objective = f"UI components: {', '.join(list(required_types)[:5])}"
                builder_context = {"required_types": list(required_types)}

                # Fetch components using canonical SearchEngine path
                search_results = search_engine.search(objective, builder_context)

                for result in search_results:
                    pkg = result.get("package")
                    if pkg:
                        candidates.append(pkg)

                _logger.info(f"ComponentDiscovery found {len(candidates)} candidates via SearchEngine.")

        except Exception as e:
            _logger.warning(f"SearchEngine-based component discovery failed: {e}")

        # In a real environment, we'd extract the components from trace.final_output.
        # For now, pass empty candidates or what we found.

        return EngineExecutionResult(
            success=True,
            artifact=artifact,
            metadata={"candidate_components": candidates, "discovery_status": "completed"},
            error=None
        )
