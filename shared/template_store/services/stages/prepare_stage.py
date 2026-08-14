# -*- coding: utf-8 -*-
from odoo import models, api

class PrepareStage(models.AbstractModel):
    _name = 'nexora.stage.preparation'
    _inherit = 'nexora.stage.base'
    _description = 'Preparation Stage'
    _stage_type = 'preparation'

    @api.model
    def execute(self, job, stage, context):
        res = self.env['nexora.workspace_preparation_service'].prepare_stage(stage, job)
        context.stage_data[str(stage.id)] = res
        return context

    @api.model
    def rollback(self, job, stage, context):
        fs = self.env['nexora.filesystem_service']
        data = context.stage_data.get(str(stage.id), {})
        for path in data.get('created_directories', []):
            fs.remove_path(path)
        return context
