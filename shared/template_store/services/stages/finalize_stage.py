# -*- coding: utf-8 -*-
from odoo import models, api

class FinalizeStage(models.AbstractModel):
    _name = 'nexora.stage.finalize'
    _inherit = 'nexora.stage.base'
    _description = 'Finalize Stage'
    _stage_type = 'finalize'

    @api.model
    def execute(self, job, stage, context):
        self.env['nexora.workspace_preparation_service'].finalize_workspace(job, stage)
        return context
