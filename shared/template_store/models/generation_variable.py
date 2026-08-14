# -*- coding: utf-8 -*-
from odoo import models, fields

class GenerationVariable(models.Model):
    _name = 'nexora.generation_variable'
    _description = 'Generation Job Substitution Variable'
    _order = 'key'

    job_id = fields.Many2one('nexora.generation_job', string='Job', required=True, ondelete='cascade')
    key = fields.Char(string='Variable Key', required=True, index=True, help="Placeholder key such as PROJECT_NAME or PORT")
    value = fields.Text(string='Variable Value')
    
    variable_type = fields.Selection([
        ('string', 'String'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
        ('json', 'JSON Object/Array'),
        ('secret', 'Secret/Token')
    ], string='Type', required=True, default='string')

    is_required = fields.Boolean(string='Required', default=False)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('job_key_uniq', 'unique(job_id, key)', 'Variable key must be unique per generation job!')
    ]
