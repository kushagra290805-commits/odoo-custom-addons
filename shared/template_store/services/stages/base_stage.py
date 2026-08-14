# -*- coding: utf-8 -*-
from odoo import models, api

class BaseStage(models.AbstractModel):
    _name = 'nexora.stage.base'
    _description = 'Base Pipeline Stage'

    _stage_type = None  # To be overridden by subclasses

    @api.model
    def execute(self, job, stage, context):
        raise NotImplementedError("Stages must implement execute()")

    @api.model
    def rollback(self, job, stage, context):
        pass

    @api.model
    def cleanup(self, job, stage, context):
        pass

    @api.model
    def checkpoint(self, job, stage, context):
        pass

    @api.model
    def supports_rollback(self):
        return True
