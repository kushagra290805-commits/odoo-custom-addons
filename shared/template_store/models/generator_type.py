# -*- coding: utf-8 -*-
from odoo import models, fields

class GeneratorType(models.Model):
    _name = 'nexora.generator_type'
    _description = 'Template Generator Type'
    _order = 'name'

    name = fields.Char(string='Type Name', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    category = fields.Selection([
        ('fullstack', 'Fullstack Web Application'),
        ('frontend', 'Frontend SPA Only'),
        ('backend', 'Backend API Only'),
        ('custom', 'Custom Architecture')
    ], string='Category', required=True, default='fullstack')
    
    description = fields.Text(string='Description')
    default_pipeline_id = fields.Many2one('nexora.generation_pipeline', string='Default Pipeline')
    capability_ids = fields.One2many('nexora.generator_capability', 'generator_type_id', string='Capabilities')
    
    metadata_json = fields.Text(string='Metadata JSON', default='{}')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The Generator Type code must be unique across the system!')
    ]
