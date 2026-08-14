# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraCapability(models.Model):
    _name = 'nexora.capability'
    _description = 'Nexora Studio Capability'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    technical_key = fields.Char(required=True)
    category_id = fields.Many2one('nexora.category', string='Category')
    provider = fields.Char()
    description = fields.Text()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('technical_key_uniq', 'unique(technical_key)', 'The technical key must be unique!')
    ]
