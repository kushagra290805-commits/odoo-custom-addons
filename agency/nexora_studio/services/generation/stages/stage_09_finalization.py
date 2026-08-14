# -*- coding: utf-8 -*-
from odoo import models, fields
import os
import json
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore

class FinalizationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.finalization'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'Stage 09: Finalization'

    def validate(self, context):
        return True

    def execute(self, context):
        session = context.builder_session
        workspace_path = context.workspace_path
        
        # Lock configuration snapshot
        if session.builder_configuration_id:
            # We assume a mechanism to lock or version the project configuration
            session.builder_configuration_id.write({'status': 'locked'})
            
        # We do not override session status here; the orchestrator or builder_session_service will handle it.
        
        # Create artifacts
        artifacts_dir = os.path.join(workspace_path, '.nexora', 'artifacts')
        os.makedirs(artifacts_dir, exist_ok=True)
        
        report = {
            'mode': getattr(context, 'mode', 'FULL'),
            'targets': getattr(context, 'targets', []),
            'force': getattr(context, 'force', False),
            'generated_files': context.get('ai_generated_files', []),
            'materialized_files': context.get('materialized_files', []),
            'runtimes': context.get('runtimes_started', [])
        }
        
        with open(os.path.join(artifacts_dir, 'generation_report.json'), 'w') as f:
            json.dump(report, f, indent=4)
            
        return GenerationStageResult(GenerationStageResult.SUCCESS, "Generation finalized.", data={'report_path': artifacts_dir})

    def rollback(self, context, execution_data):
        session = context.builder_session
        session.write({'status': 'draft'})
        if session.builder_configuration_id:
            session.builder_configuration_id.write({'status': 'draft'})
