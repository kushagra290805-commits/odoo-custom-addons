# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraNavigation(models.Model):
    _name = 'nexora.navigation'
    _description = 'Nexora Studio Navigation'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    technical_key = fields.Char(required=True)
    parent_id = fields.Many2one('nexora.navigation', string='Parent')
    action_xmlid = fields.Char(string='Action XML ID')
    description = fields.Text()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('technical_key_uniq', 'unique(technical_key)', 'The technical key must be unique!')
    ]
