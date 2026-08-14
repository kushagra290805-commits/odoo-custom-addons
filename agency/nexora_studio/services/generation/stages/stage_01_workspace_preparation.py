# -*- coding: utf-8 -*-
from odoo import models
import os
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore

class WorkspacePreparationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.workspace_preparation'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'Stage 01: Workspace Preparation'

    def validate(self, context):
        if not context.builder_session:
            raise ValueError("Builder session is required for Workspace Preparation.")
        if not context.builder_session.workspace_id:
            raise ValueError("Workspace ID is not assigned to the builder session.")
        return True

    def execute(self, context):
        workspace = context.builder_session.workspace_id
        path = workspace.workspace_path
        
        if not os.path.exists(path):
            os.makedirs(path)
            
        directories_to_create = ['.nexora', 'src', 'public', 'config']
        created_dirs = []
        for d in directories_to_create:
            full_path = os.path.join(path, d)
            if not os.path.exists(full_path):
                os.makedirs(full_path)
                created_dirs.append(full_path)
                
        context.set('created_directories', created_dirs)
        
        # Init workspace metadata
        metadata_path = os.path.join(path, '.nexora', 'workspace_meta.json')
        if not os.path.exists(metadata_path):
            import json
            with open(metadata_path, 'w') as f:
                json.dump({"initialized": True, "session_id": context.builder_session.id}, f)
            context.set('metadata_initialized', True)
            
        return GenerationStageResult(GenerationStageResult.SUCCESS, "Workspace prepared.", data={'created': created_dirs})

    def rollback(self, context, execution_data):
        created_dirs = execution_data.get('created', [])
        for d in created_dirs:
            if os.path.exists(d):
                try:
                    os.rmdir(d) # Only removes if empty, which is safe for rollback
                except OSError:
                    pass
