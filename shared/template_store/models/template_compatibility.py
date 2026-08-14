# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class TemplateCompatibility(models.Model):
    _name = 'nexora.template_compatibility'
    _description = 'Template Compatibility Matrix'
    _order = 'compatibility_level asc, id desc'

    name = fields.Char(
        string="Compatibility Pair",
        compute="_compute_name",
        store=True,
        readonly=True
    )
    frontend_template_id = fields.Many2one(
        'nexora.template_frontend',
        string="Frontend Template",
        required=True,
        ondelete='cascade'
    )
    backend_template_id = fields.Many2one(
        'nexora.template_backend',
        string="Backend Template",
        required=True,
        ondelete='cascade'
    )
    compatibility_level = fields.Selection([
        ('verified', 'Verified Production Ready'),
        ('compatible', 'Standard Compatible'),
        ('experimental', 'Experimental / Beta'),
        ('incompatible', 'Incompatible / Unsupported')
    ], string="Compatibility Level", default='verified', required=True)
    notes = fields.Text(
        string="Integration Notes",
        help="Special configuration requirements when pairing these two templates."
    )
    active = fields.Boolean(string="Active", default=True)

    @api.depends('frontend_template_id.name', 'backend_template_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.frontend_template_id and rec.backend_template_id:
                rec.name = f"{rec.frontend_template_id.name} <-> {rec.backend_template_id.name}"
            else:
                rec.name = "New Compatibility Pair"

    _sql_constraints = [
        ('pair_uniq', 'unique(frontend_template_id, backend_template_id)', 'A compatibility definition already exists for this exact Frontend and Backend template pair!')
    ]
