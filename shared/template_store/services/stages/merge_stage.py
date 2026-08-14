# -*- coding: utf-8 -*-
from odoo import models, api

class MergeStage(models.AbstractModel):
    _name = 'nexora.stage.merge'
    _inherit = 'nexora.stage.base'
    _description = 'Merge Stage'
    _stage_type = 'merge'

    @api.model
    def execute(self, job, stage, context):
        res = self.env['nexora.merge_service'].merge_templates_interface(job, stage)
        context.stage_data[str(stage.id)] = res
        return context

    @api.model
    def rollback(self, job, stage, context):
        fs = self.env['nexora.filesystem_service']
        data = context.stage_data.get(str(stage.id), {})
        for f in data.get('merged', []):
            path = job.target_workspace_path + '/shared/' + f
            fs.remove_path(path)
