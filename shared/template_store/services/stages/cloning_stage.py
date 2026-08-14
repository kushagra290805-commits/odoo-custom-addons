# -*- coding: utf-8 -*-
from odoo import models, api

class CloningStage(models.AbstractModel):
    _name = 'nexora.stage.cloning'
    _inherit = 'nexora.stage.base'
    _description = 'Cloning Stage'
    _stage_type = 'cloning'

    @api.model
    def execute(self, job, stage, context):
        res = self.env['nexora.generation_service'].execute_stage_cloning(stage, job)
        context.stage_data[str(stage.id)] = res
        return context

    @api.model
    def rollback(self, job, stage, context):
        fs = self.env['nexora.filesystem_service']
        data = context.stage_data.get(str(stage.id), {})
        for path in data.get('copied_paths', []):
            fs.remove_path(path)
