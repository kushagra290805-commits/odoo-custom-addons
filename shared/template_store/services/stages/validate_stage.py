# -*- coding: utf-8 -*-
from odoo import models, api

class ValidateStage(models.AbstractModel):
    _name = 'nexora.stage.validation'
    _inherit = 'nexora.stage.base'
    _description = 'Validation Stage'
    _stage_type = 'validation'

    @api.model
    def execute(self, job, stage, context):
        self.env['nexora.validation_service'].validate_stage_requirements(stage, job)
        context.execution_metadata['validation_passed'] = True
        return context
