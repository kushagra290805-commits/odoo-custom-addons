# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraCategory(models.Model):
    _name = 'nexora.category'
    _description = 'Nexora Studio Category'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    technical_key = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('technical_key_uniq', 'unique(technical_key)', 'The technical key must be unique!')
    ]
