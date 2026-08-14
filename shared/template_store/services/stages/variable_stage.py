# -*- coding: utf-8 -*-
from odoo import models, api

class VariableStage(models.AbstractModel):
    _name = 'nexora.stage.variable'
    _inherit = 'nexora.stage.base'
    _description = 'Variable Stage'
    _stage_type = 'variable'

    @api.model
    def execute(self, job, stage, context):
        self.env['nexora.variable_engine'].execute_stage_variables(stage, job)
        return context
