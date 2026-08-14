from abc import ABC, abstractmethod
from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.workflow_context import WorkflowContext
from odoo.addons.nexora_studio.services.generation.workflows.workflow_descriptor import WorkflowDescriptor

class BaseWorkflow(ABC):
    def __init__(self, descriptor: WorkflowDescriptor):
        self.descriptor = descriptor
        
    @abstractmethod
    def execute(self, context: WorkflowContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass

class WorkflowFactory:
    """
    Instantiates concrete Workflow classes from descriptors.
    """
    def __init__(self):
        self._builders = {}
        
    def register_builder(self, workflow_id: str, builder_func) -> None:
        self._builders[workflow_id] = builder_func
        
    def create_workflow(self, descriptor: WorkflowDescriptor) -> BaseWorkflow:
        builder = self._builders.get(descriptor.id)
        if not builder:
            raise ValueError(f"No builder registered for workflow: {descriptor.id}")
        return builder(descriptor)
