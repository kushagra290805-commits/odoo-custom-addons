# -*- coding: utf-8 -*-
from odoo import models, fields

class GenerationPipeline(models.Model):
    _name = 'nexora.generation_pipeline'
    _description = 'Template Generation Pipeline'
    _order = 'name'

    name = fields.Char(string='Pipeline Name', required=True)
    code = fields.Char(string='Pipeline Code', required=True, index=True)
    generator_type_id = fields.Many2one('nexora.generator_type', string='Target Generator Type')
    description = fields.Text(string='Description')
    
    stage_ids = fields.One2many('nexora.generation_stage', 'pipeline_id', string='Generation Stages')
    
    metadata_json = fields.Text(string='Metadata JSON', default='{}')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The Pipeline code must be unique!')
    ]
