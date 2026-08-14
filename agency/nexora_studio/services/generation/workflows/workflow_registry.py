from typing import Dict, List, Optional
from odoo.addons.nexora_studio.services.generation.workflows.workflow_descriptor import WorkflowDescriptor
from odoo.addons.nexora_studio.services.generation.workflows.workflow_factory import WorkflowFactory, BaseWorkflow

class WorkflowRegistry:
    """
    Stores and manages available workflow descriptors.
    Flow: WorkflowDescriptor -> WorkflowFactory -> WorkflowRegistry
    """
    def __init__(self, factory: WorkflowFactory):
        self.factory = factory
        self._descriptors: Dict[str, WorkflowDescriptor] = {}
        
    def register_descriptor(self, descriptor: WorkflowDescriptor) -> None:
        self._descriptors[descriptor.id] = descriptor
        
    def get_workflow(self, workflow_id: str) -> BaseWorkflow:
        descriptor = self._descriptors.get(workflow_id)
        if not descriptor:
            raise ValueError(f"Workflow {workflow_id} not found.")
        return self.factory.create_workflow(descriptor)
        
    def list_workflows(self) -> List[WorkflowDescriptor]:
        return list(self._descriptors.values())
