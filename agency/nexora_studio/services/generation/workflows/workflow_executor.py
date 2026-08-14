from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.workflow_context import WorkflowContext
from odoo.addons.nexora_studio.services.generation.workflows.workflow_registry import WorkflowRegistry

class WorkflowExecutor:
    """
    The engine that kicks off workflows and passes the context to them.
    """
    def __init__(self, registry: WorkflowRegistry):
        self.registry = registry
        
    def run_workflow(self, workflow_id: str, payload: Dict[str, Any], context: WorkflowContext) -> Dict[str, Any]:
        workflow = self.registry.get_workflow(workflow_id)
        return workflow.execute(context, payload)
