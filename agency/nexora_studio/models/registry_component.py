# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraComponent(models.Model):
    _name = 'nexora.component'
    _description = 'Nexora Studio Component'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    technical_name = fields.Char(required=True)
    semantic_version = fields.Char()
    module_name = fields.Char()
    description = fields.Text()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('technical_name_uniq', 'unique(technical_name)', 'The technical name must be unique!')
    ]
