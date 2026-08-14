# -*- coding: utf-8 -*-
from odoo import models
# pyrefly: ignore [missing-import]
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult
# type: ignore

class AbstractGenerationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage'
    _description = 'Abstract Generation Stage'

    def get_stage_name(self):
        return self._name

    def get_required_capabilities(self):
        """Return a list of capability codes required by this stage."""
        return []

    def validate(self, context, **kwargs):
        """Validate if the stage can be executed."""
        return True

    def execute(self, context, **kwargs):
        """Execute the generation stage logic."""
        raise NotImplementedError("Stages must implement execute()")

    def rollback(self, context, **kwargs):
        """Rollback the changes made during execute."""
        pass
