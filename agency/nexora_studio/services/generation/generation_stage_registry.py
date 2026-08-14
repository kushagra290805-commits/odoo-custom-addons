# -*- coding: utf-8 -*-
from odoo import models, api

class GenerationStageRegistry(models.AbstractModel):
    _name = 'nexora.generation_stage_registry'
    _description = 'Generation Stage Registry'

    @api.model
    def get_stages(self):
        """Returns the ordered list of generation stages."""
        stage_names = [
            'nexora.ai_generation_stage.workspace_preparation',
            'nexora.ai_generation_stage.template_resolution',
            'nexora.ai_generation_stage.template_materialization',
            'nexora.ai_generation_stage.variable_injection',
            'nexora.ai_generation_stage.dependency_resolution',
            'nexora.ai_generation_stage.ai_code_generation',
            'nexora.ai_generation_stage.runtime_bootstrap',
            'nexora.ai_generation_stage.validation',
            'nexora.ai_generation_stage.self_review',
            'nexora.ai_generation_stage.bug_fix',
            'nexora.ai_generation_stage.quality_pass',
            'nexora.ai_generation_stage.security_review',
            'nexora.ai_generation_stage.finalization',
        ]
        
        stages = []
        for name in stage_names:
            stage_model = self.env.get(name)
            if stage_model is not None:
                stages.append(stage_model)
        return stages
