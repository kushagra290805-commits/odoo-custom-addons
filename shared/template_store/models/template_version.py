# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TemplateVersion(models.Model):
    _name = 'nexora.template_version'
    _description = 'Template Version Tracker'
    _order = 'release_date desc, id desc'

    name = fields.Char(string="Version Identifier", required=True, help="e.g. v1.0.0, v2.1.0-beta")
    frontend_template_id = fields.Many2one(
        'nexora.template_frontend',
        string="Frontend Template",
        ondelete='cascade'
    )
    backend_template_id = fields.Many2one(
        'nexora.template_backend',
        string="Backend Template",
        ondelete='cascade'
    )
    commit_hash = fields.Char(string="Commit Hash / Tag", help="Exact Git commit hash or tag corresponding to this release.")
    release_notes = fields.Text(string="Release Notes")
    is_latest = fields.Boolean(string="Is Latest Version", default=True)
    release_date = fields.Date(string="Release Date", default=fields.Date.today)
    active = fields.Boolean(string="Active", default=True)

    @api.constrains('frontend_template_id', 'backend_template_id')
    def _check_template_target(self):
        for rec in self:
            if not rec.frontend_template_id and not rec.backend_template_id:
                raise ValidationError(_("A template version must belong to either a Frontend Template or a Backend Template."))
            if rec.frontend_template_id and rec.backend_template_id:
                raise ValidationError(_("A template version cannot belong to both Frontend and Backend templates simultaneously."))
