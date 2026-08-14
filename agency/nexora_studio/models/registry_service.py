# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraService(models.Model):
    _name = 'nexora.service'
    _description = 'Nexora Studio Service'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    technical_key = fields.Char(required=True)
    service_type = fields.Char()
    endpoint = fields.Char()
    status = fields.Char()
    description = fields.Text()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('technical_key_uniq', 'unique(technical_key)', 'The technical key must be unique!')
    ]
