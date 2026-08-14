from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.workflow_factory import BaseWorkflow
from odoo.addons.nexora_studio.services.generation.workflows.generation_pipeline import GenerationPipeline

class WebsiteGenerationWorkflow(BaseWorkflow):
    """
    Concrete implementation defining the full website generation sequence.
    """
    def __init__(self, descriptor, pipeline: GenerationPipeline):
        super().__init__(descriptor)
        self.pipeline = pipeline
        
    def execute(self, context, payload: Dict[str, Any]) -> Dict[str, Any]:
        reqs = payload.get("client_requirements", "")
        self.pipeline.execute(reqs, context)
        return {"status": "completed"}
