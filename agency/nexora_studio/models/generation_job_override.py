# -*- coding: utf-8 -*-
from odoo import models, fields, api

class GenerationJobOverride(models.Model):
    _inherit = 'nexora.generation_job'

    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', ondelete='cascade')
    assigned_model_id = fields.Many2one('nexora.ai_model_catalog', string='Assigned Model', help='Deterministic canonical model assignment overriding provider defaults for this job.')
    temperature = fields.Float(string='Temperature', default=0.7)
    capability_requirements = fields.Char(string='Capability Requirements')
    priority = fields.Integer(string='Priority', default=10)

    def action_start_generation(self):
        super().action_start_generation()
        for record in self:
            self.env['nexora.generation_orchestrator'].execute_job(record)
        return True

    def action_rollback(self):
        super().action_rollback()
        for record in self:
            self.env['nexora.generation_orchestrator'].rollback_job(record)
        return True
