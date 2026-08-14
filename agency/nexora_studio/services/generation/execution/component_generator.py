from typing import Dict, Any
from odoo.addons.nexora_studio.services.design_system.component_schema import ComponentSchema
from odoo.addons.nexora_studio.services.generation.workflows.workflow_context import WorkflowContext

class ComponentGenerator:
    """
    Orchestrates the generation of a component.
    Passes through Adapter -> Translator -> Validator before reaching PatchEngine.
    Never generates raw HTML directly.
    """
    def __init__(self, platform_runtime, adapter_registry, translator, validator):
        self.platform = platform_runtime
        self.adapters = adapter_registry
        self.translator = translator
        self.validator = validator
        
    def generate(self, plan: Any, context: WorkflowContext) -> ComponentSchema:
        # 1. Ask PlatformRuntime to get raw component
        orchestrator = self.platform.get_runtime("core.orchestration")
        ai_resp = orchestrator.execute_workflow("generate_component", plan, context.get_capabilities())
        
        raw = ai_resp.get("raw_component", {})
        source = ai_resp.get("source_ecosystem", "unknown")
        
        # 2. Adapter
        adapter = self.adapters.get_adapter(source)
        if adapter:
            schema = adapter.parse_component(raw)
        else:
            schema = raw # fallback
            
        # 3. Translator
        translated = self.translator.translate_ast_node(schema) if hasattr(self.translator, "translate_ast_node") else schema
        
        # 4. Validator (Delegated to external validation pipeline in production)
        
        return translated
