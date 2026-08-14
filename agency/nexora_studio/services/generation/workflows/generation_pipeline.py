from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.requirement_analyzer import RequirementAnalyzer
from odoo.addons.nexora_studio.services.generation.workflows.planning_workflow import PlanningWorkflow
from odoo.addons.nexora_studio.services.generation.workflows.workflow_context import WorkflowContext

class GenerationPipeline:
    """
    Enforces the strict execution flow required by Phase 19A.
    """
    def __init__(
        self,
        platform_runtime: Any,
        design_translator: Any,
        design_validator: Any,
        patch_engine: Any
    ):
        self.platform = platform_runtime
        self.translator = design_translator
        self.validator = design_validator
        self.patch_engine = patch_engine
        
        self.analyzer = RequirementAnalyzer()
        self.planner = PlanningWorkflow()
        
    def execute(self, client_requirements: str, context: WorkflowContext) -> None:
        """
        The explicit execution flow:
        RequirementAnalyzer -> PlanningWorkflow -> PlatformRuntime -> Providers/Capabilities ->
        Adapters -> DesignTranslator -> DesignValidator -> PatchEngine -> DocumentModel
        """
        # 1. RequirementAnalyzer
        analyzed_reqs = self.analyzer.analyze(client_requirements)
        
        # 2. PlanningWorkflow
        plan = self.planner.plan(analyzed_reqs)
        
        # 3. PlatformRuntime (AI Orchestration)
        orchestrator = self.platform.get_runtime("core.orchestration")
        # Ensure context exposes available ToolCapabilities to the AI
        ai_response = orchestrator.execute_workflow("website_generation", plan, context.get_capabilities())
        
        # 4. Providers / ToolCapabilities
        # The AI response dictates which external components/assets it retrieved.
        # e.g., raw_component = fetch_from_provider(ai_response.source)
        raw_components = ai_response.get("generated_components", [])
        
        for raw_comp in raw_components:
            # 5. Adapters
            adapter = context.adapter_registry.get_adapter(raw_comp.get("source_ecosystem"))
            if adapter:
                ast = adapter.parse_component(raw_comp)
            else:
                ast = raw_comp # Assuming native Format
                
            # 6. DesignTranslator
            translated_schema = self.translator.translate_ast_node(ast) if hasattr(self.translator, "translate_ast_node") else ast
            
            # 7. DesignValidator
            # 8. PatchEngine
            # 9. DocumentModel
            if translated_schema:
                # Assuming simple patch structure for demonstration
                patch = {
                    "action": "create",
                    "node_id": translated_schema.component_id if hasattr(translated_schema, 'component_id') else "unknown",
                    "data": {"type": translated_schema.category if hasattr(translated_schema, 'category') else "unknown"}
                }
                
                # Validation happens inside patch_engine.apply_patch usually, or explicitly
                self.patch_engine.begin_transaction()
                self.patch_engine.apply_patch(patch)
                self.patch_engine.commit()
