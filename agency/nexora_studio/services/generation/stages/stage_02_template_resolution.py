# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
import os
import logging

_logger = logging.getLogger(__name__)

class TemplateResolutionStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.template_resolution'
    _inherit = 'nexora.ai_generation_stage'
    _description = 'Stage 02: Template Resolution'

    def validate(self, context):
        if not context.builder_session.builder_configuration_id:
            raise ValueError("Project configuration is missing.")
        return True

    def execute(self, context):
        # Look for the selected template via Template Store
        # Currently, if a project doesn't have a specific template stored, we default to the first active one,
        # or fallback to the local vite-react template if none are found in the DB.
        
        template_record = self.env['nexora.template_frontend'].search([('active', '=', True)], limit=1)
        
        if template_record and template_record.git_repo_url and template_record.git_repo_url.startswith('file://'):
            template_path = template_record.git_repo_url.replace('file://', '')
        elif template_record and template_record.subfolder_path:
            # Construct from addon path if it's a local template
            # For robustness, we fallback to the known local path if not explicitly configured
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            template_path = os.path.join(base_path, 'assets', 'frontend-templates', 'vite-react')
        else:
            # Hard fallback for development/testing
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            template_path = os.path.join(base_path, 'assets', 'frontend-templates', 'vite-react')
            
        template_path = os.path.abspath(template_path)
        
        if not os.path.exists(template_path):
            raise Exception(f"Resolved template path does not exist: {template_path}")
            
        _logger.info(f"Resolved template path: {template_path}")
        context.set('template_path', template_path)
        context.set('resolved_template_id', template_record.id if template_record else None)
        
        return GenerationStageResult(GenerationStageResult.SUCCESS, f"Template resolved from store: {template_record.name if template_record else 'Default Vite-React'}", data={'template_path': template_path, 'template_id': template_record.id if template_record else None})

    def rollback(self, context, execution_data):
        context.set('template_path', None)
        context.set('resolved_template_id', None)
