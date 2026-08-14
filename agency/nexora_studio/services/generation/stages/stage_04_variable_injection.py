# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
import os

class VariableInjectionStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.variable_injection'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'Stage 04: Variable Injection'

    def execute(self, context):
        workspace_path = context.workspace_path
        target_src = os.path.join(workspace_path, 'src')
        
        # Build injection payload from context and session
        session = context.builder_session
        config = session.builder_configuration_id
        
        assignment = self.env['nexora.developer_assignment'].search([('builder_session_id', '=', session.id)], limit=1)
        client_name = 'Unknown Client'
        project_name = config.name
        
        if assignment and assignment.request_id:
            req = assignment.request_id
            if req.project_id:
                project_name = req.project_id.name
                if req.project_id.partner_id:
                    client_name = req.project_id.partner_id.name
            elif req.requirements_id and req.requirements_id.business_name:
                client_name = req.requirements_id.business_name
        
        variables = {
            'project_name': project_name,
            'environment': config.environment,
            'session_uuid': session.session_uuid,
            'workspace_path': workspace_path,
            'client_name': client_name
        }
        
        # Add any variables loaded from context (e.g., from template metadata)
        if context.get('template_metadata'):
            variables['template'] = context.get('template_metadata')
            
        injector = self.env['nexora.variable_injection_service']
        
        try:
            result = injector.inject_variables(target_src, variables)
            context.set('injected_files_count', result['success'])
            
            if result['errors'] > 0:
                self.env['nexora.runtime_event'].create({
                    'builder_session_id': session.id,
                    'runtime_type': 'workspace',
                    'event_type': 'generation.warning',
                    'message': f"Variable injection had {result['errors']} errors."
                })
                
        except Exception as e:
            return GenerationStageResult(GenerationStageResult.FAILURE, f"Variable injection failed: {str(e)}")
            
        return GenerationStageResult(GenerationStageResult.SUCCESS, f"Variables injected into {result['success']} files.")

    def rollback(self, context, execution_data):
        # Variable injection modifies files in place. Rollback is handled by Materialization Stage wiping the files,
        # or in incremental generation, restoring from Diff Engine checkpoints.
        pass
