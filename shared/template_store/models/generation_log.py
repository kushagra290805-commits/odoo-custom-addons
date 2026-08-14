# -*- coding: utf-8 -*-
from odoo import models, fields

class GenerationLog(models.Model):
    _name = 'nexora.generation_log'
    _description = 'Generation Job Execution Log'
    _order = 'timestamp asc, id asc'

    job_id = fields.Many2one('nexora.generation_job', string='Job', required=True, ondelete='cascade', index=True)
    stage_id = fields.Many2one('nexora.generation_stage', string='Stage', ondelete='set null')
    
    timestamp = fields.Datetime(string='Timestamp', required=True, default=fields.Datetime.now)
    level = fields.Selection([
        ('debug', 'DEBUG'),
        ('info', 'INFO'),
        ('warning', 'WARNING'),
        ('error', 'ERROR')
    ], string='Level', required=True, default='info')

    message = fields.Text(string='Message', required=True)
    details_json = fields.Text(string='Telemetry Details JSON')
