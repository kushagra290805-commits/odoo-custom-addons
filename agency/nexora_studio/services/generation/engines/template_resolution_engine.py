import logging
import os
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, TemplateResolution

_logger = logging.getLogger(__name__)

class TemplateResolutionEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing TemplateResolutionEngine...")
        
        env = self.orchestrator.env
        
        template_record = env['nexora.template_frontend'].search([('active', '=', True)], limit=1)
        
        if template_record and template_record.git_repo_url and template_record.git_repo_url.startswith('file://'):
            template_path = template_record.git_repo_url.replace('file://', '')
        elif template_record and template_record.subfolder_path:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            template_path = os.path.join(base_path, 'assets', 'frontend-templates', 'vite-react')
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            template_path = os.path.join(base_path, 'assets', 'frontend-templates', 'vite-react')
            
        template_path = os.path.abspath(template_path)
        
        if not os.path.exists(template_path):
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=f"Resolved template path does not exist: {template_path}")
            
        _logger.info(f"Resolved template path: {template_path}")
        
        model = TemplateResolution(
            template_id=template_record.id if template_record else 0,
            template_name=template_record.name if template_record else "Default Vite-React",
            template_path=template_path,
            template_source="local" if "assets" in template_path else "git",
            template_metadata={},
            template_capabilities=[],
            template_variables={}
        )
        
        return EngineExecutionResult(success=True, artifact=artifact.evolve(template=model), metadata={"template_path": template_path}, error=None)
