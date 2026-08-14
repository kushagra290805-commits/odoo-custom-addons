import unittest
from unittest.mock import MagicMock, patch
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    GenerationContext, GenerationState, RequirementModel, WebsiteGenerationArtifact
)
from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import WebsiteGenerationPipeline
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory


@tagged('post_install', '-at_install', 'phase16')
class TestPhase16GenerationPipeline(TransactionCase):
    def setUp(self):
        super().setUp()
        self.orchestrator = MagicMock()
        self.state_manager = MagicMock()
        self.state_manager.check_interruption.return_value = False
        self.state_manager.update_progress.side_effect = lambda ctx, nxt, pct, msg: ctx.evolve(state=nxt)
        self.state_manager.rollback.return_value = None
        self.state_manager.cancel.side_effect = lambda ctx: ctx.evolve(state=GenerationState.FAILED)

        mock_env = MagicMock()
        mock_env.__getitem__.return_value.search.return_value = False
        mock_env.__getitem__.return_value.validate_design.return_value = {
            "issues": [],
            "scores": {"accessibility": 100, "performance": 100}
        }
        self.orchestrator.env = mock_env
        self.pipeline = WebsiteGenerationPipeline(self.orchestrator, self.state_manager)

    def test_01_full_generation_pipeline(self):
        """
        Verifies the full deterministic pipeline produces a correctly structured artifact.

        Contracts verified:
        1. Domain classification produces a non-empty, known-domain value.
        2. Content pages are non-empty.
        3. Homepage "/" route exists in generated pages.
        4. Component tree contains generated nodes.
        5. Architecture has a non-empty layout strategy.
        6. Validation passed.
        7. Workspace is ready.
        """
        ctx = GenerationContext(
            context_id="test-session",
            artifact=WebsiteGenerationArtifact(
                requirements=RequirementModel(
                    raw_input="Build me a dev tool SaaS website with a blog."
                )
            )
        )
        runtime = MagicMock()
        runtime.metadata.session_id = "12345"
        runtime.get_scoped_view.return_value = runtime

        from odoo.addons.nexora_studio.services.generation.engines.base_engine import EngineExecutionResult
        from odoo.addons.nexora_studio.services.generation.engines.component_discovery_engine import ComponentDiscoveryEngine
        from odoo.addons.nexora_studio.services.generation.core.generation_context import ComponentTree

        def mock_discovery_execute(self_engine, artifact, rt):
            nodes = list(artifact.component_tree.nodes) if hasattr(artifact.component_tree, 'nodes') else []
            deps = list(artifact.component_tree.dependencies) if hasattr(artifact.component_tree, 'dependencies') else []
            nodes.append({
                "provider": "nexora_dynamic",
                "component_id": "hero",
                "code": "/* hero code tailwind */",
                "score": 1.0,
                "metadata": {"source_identifier": "hero"}
            })
            if "tailwindcss" not in deps:
                deps.append("tailwindcss")

            new_tree = ComponentTree(nodes=nodes, dependencies=deps)
            return EngineExecutionResult(
                success=True,
                artifact=artifact.evolve(component_tree=new_tree),
                metadata={"candidate_components": [{"component_id": "hero"}], "discovery_status": "delegated_to_composition_engine"},
                error=None
            )

        with patch.object(ComponentDiscoveryEngine, 'execute', mock_discovery_execute):
            context = self.pipeline.run(ctx, runtime=runtime)

        self.assertEqual(context.state, GenerationState.COMPLETED)

        # 1. Domain classification: "SaaS" keyword detected
        self.assertEqual(context.artifact.requirements.domain, "SaaS",
            "RequirementEngine must classify the domain as SaaS")

        # 2. Features: BlogSystem must exist
        self.assertIn("BlogSystem", context.artifact.requirements.features,
            "RequirementEngine must detect the BlogSystem feature")

        # 3. Architecture layout strategy
        self.assertEqual(context.artifact.architecture.layout_strategy, "Sidebar",
            "ArchitectureEngine must produce a Sidebar layout strategy for SaaS")

        # 4. Content pages (routes) must be defined in the architecture
        pages = [data.get("path") for comp_id, data in context.artifact.architecture.component_hierarchy.items() if data.get("type") == "page"]
        self.assertGreater(len(pages), 0,
            "ArchitectureEngine must generate at least one page route in component_hierarchy")

        # 5. Homepage "/" must exist
        self.assertIn("/", pages,
            "ArchitectureEngine must produce a homepage route '/'")

        # 6. Component tree must contain nodes and tailwindcss dependency
        self.assertGreater(len(context.artifact.component_tree.nodes), 0,
            "ComponentDiscoveryEngine must populate component_tree.nodes")
        self.assertIn("tailwindcss", context.artifact.component_tree.dependencies,
            "ComponentDiscoveryEngine must include tailwindcss as a dependency")

        # 7. Theme contract
        self.assertNotEqual(context.artifact.theme.colors.get("background"), "",
            "ThemeEngine must produce a non-empty background color")

        # 8. Asset contract
        self.assertGreater(len(context.artifact.assets.images), 0,
            "AssetEngine must produce at least one image asset")

        # 9. Validation must pass (ValidationEngine runs at end of pipeline)
        self.assertTrue(context.artifact.validation.passed,
            "ValidationEngine must report passed=True for a valid generated artifact")

        # 10. Workspace must be marked ready (WorkspaceGeneratorEngine contract)
        self.assertTrue(context.artifact.workspace.is_ready,
            "WorkspaceGeneratorEngine must mark workspace.is_ready=True")

    def test_02_pipeline_interruption(self):
        """
        Verifies that a pipeline that receives an interruption signal transitions to INTERRUPTED.
        """
        context_id = "test-interrupt"
        ctx = GenerationContext(context_id=context_id)
        self.pipeline.state_manager.save_checkpoint(ctx)
        self.pipeline.state_manager.interrupt(context_id)
        self.pipeline.state_manager.check_interruption.return_value = True
        runtime = MagicMock()
        runtime.metadata.session_id = "12345"
        runtime.get_scoped_view.return_value = runtime
        context = self.pipeline.run(
            ctx.evolve(artifact=WebsiteGenerationArtifact(
                requirements=RequirementModel(raw_input="Build me a dev tool SaaS website.")
            )),
            runtime=runtime
        )
        self.assertEqual(context.state, GenerationState.INTERRUPTED)

    def test_03_pipeline_retry_and_recovery(self):
        """
        Verifies the pipeline's built-in retry mechanism.

        The pipeline is configured with max_retries=2 (1 initial attempt + 1 retry).
        We inject a ConnectionError on the first execute() call of RequirementEngine.
        The pipeline's retry loop must catch it, retry once, succeed, and complete.

        Contracts verified:
        - First attempt raises (fail)
        - Retry occurs exactly once (call_count == 2)
        - Pipeline ultimately reaches COMPLETED state
        """
        ctx = GenerationContext(
            context_id="test-retry",
            artifact=WebsiteGenerationArtifact(
                requirements=RequirementModel(raw_input="Build me a dev tool SaaS website.")
            )
        )
        runtime = MagicMock()
        runtime.metadata.session_id = "12345"
        runtime.get_scoped_view.return_value = runtime

        # Inject a transient failure into RequirementEngine's execute() method.
        # This is the real execution path that the pipeline's retry loop covers.
        call_count = {"n": 0}
        req_engine = self.pipeline.registry[GenerationState.PENDING][0]
        original_execute = req_engine.__class__.execute

        def patched_execute(self_engine, artifact, rt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("Simulated transient failure")
            return original_execute(self_engine, artifact, rt)

        with patch.object(req_engine.__class__, 'execute', patched_execute):
            context = self.pipeline.run(ctx, runtime=runtime)

        self.assertEqual(context.state, GenerationState.COMPLETED)
        # Pipeline max_retries=2: exactly 1 failed attempt + 1 successful retry = 2 calls total
        self.assertEqual(call_count["n"], 2,
            "Pipeline retry contract: exactly 1 initial failure + 1 successful retry expected")
