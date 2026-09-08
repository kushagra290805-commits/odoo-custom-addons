import logging
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

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
            env = runtime.env

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
                search_results = search_engine.search(
                    objective,
                    builder_context,
                    operation='COMPONENT_SOURCE',
                )

                candidates.extend(search_results)
                provider_errors = list(search_engine.provider_errors)

                _logger.info(f"ComponentDiscovery found {len(candidates)} candidates via SearchEngine.")

        except Exception as e:
            _logger.warning(f"SearchEngine-based component discovery failed: {e}")

        provider_errors = locals().get('provider_errors', [])

        # Phase 45 (ADR-0072): publish ranked candidates on the artifact bus so
        # downstream engines (ComponentIntelligenceEngine) can consume them —
        # result.metadata alone never reaches other engines (pipeline merges
        # it into context.metadata, which engines do not receive).
        artifact = artifact.evolve(generation_metadata={
            **artifact.generation_metadata,
            "candidate_components": candidates,
            "component_provider_errors": provider_errors,
        })

        return EngineExecutionResult(
            success=True,
            artifact=artifact,
            metadata={
                "candidate_components": candidates,
                "component_provider_errors": provider_errors,
                "discovery_status": "completed",
            },
            error=None
        )
