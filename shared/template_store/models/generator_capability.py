# -*- coding: utf-8 -*-
from odoo import models, fields

class GeneratorCapability(models.Model):
    _name = 'nexora.generator_capability'
    _description = 'Template Generator Capability'
    _order = 'name'

    name = fields.Char(string='Capability Name', required=True)
    code = fields.Char(string='Technical Code', required=True, index=True)
    generator_type_id = fields.Many2one('nexora.generator_type', string='Generator Type', ondelete='cascade')
    description = fields.Text(string='Description')
    metadata_json = fields.Text(string='Metadata JSON', default='{}')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The Capability code must be unique!')
    ]
