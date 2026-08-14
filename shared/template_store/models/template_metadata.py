# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json

class TemplateMetadata(models.Model):
    _name = 'nexora.template_metadata'
    _description = 'Template Schema & Configuration Specification'
    _order = 'name asc'

    name = fields.Char(string="Schema Title", required=True, help="e.g. Standard Fullstack Metadata Schema")
    schema_version = fields.Char(string="Schema Version", default="1.0", required=True)
    author = fields.Char(string="Author / Maintainer", default="Nexora Engineering")
    tags = fields.Char(string="Tags / Categories", help="Comma-separated tags (e.g. spa, rest, postgres)")
    raw_json = fields.Text(
        string="Schema JSON Definition",
        default='{\n  "required_variables": ["PROJECT_NAME", "PORT", "API_URL"],\n  "default_ports": {"frontend": 3000, "backend": 8000},\n  "env_mapping": {}\n}',
        help="Structured JSON specification describing required environment keys and architecture metadata."
    )
    active = fields.Boolean(string="Active", default=True)

    @api.constrains('raw_json')
    def _check_valid_json(self):
        for rec in self:
            if rec.raw_json:
                try:
                    json.loads(rec.raw_json)
                except Exception as e:
                    raise ValidationError(_(f"Invalid JSON in Schema Specification '{rec.name}': {e}"))
