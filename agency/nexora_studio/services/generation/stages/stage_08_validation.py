# -*- coding: utf-8 -*-
from odoo import models
import os
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore

class ValidationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.validation'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'Stage 08: Validation'

    def execute(self, context):
        workspace_path = context.workspace_path
        target_src = os.path.join(workspace_path, 'src')
        
        session = context.builder_session
        
        if not os.path.exists(target_src):
            return GenerationStageResult(GenerationStageResult.FAILURE, "Validation failed: src directory is missing.")
            
        # Call diff service to hash files
        diff_service = self.env['nexora.generation_diff_service']
        hashes = diff_service.calculate_workspace_hashes(target_src)
        
        # Create manifest
        manifest_service = self.env['nexora.artifact_manifest_service']
        manifest = manifest_service.create_manifest(workspace_path, context.state, hashes)
        
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'workspace',
            'event_type': 'generation.validation.completed',
            'message': f"Validation passed. Artifact manifest created with {len(hashes)} files."
        })
        
        return GenerationStageResult(GenerationStageResult.SUCCESS, "Workspace validated and manifest generated.", data={'manifest': manifest})

    def rollback(self, context, execution_data):
        manifest_path = os.path.join(context.workspace_path, '.nexora', 'manifest.json')
        if os.path.exists(manifest_path):
            try:
                os.remove(manifest_path)
            except OSError:
                pass
