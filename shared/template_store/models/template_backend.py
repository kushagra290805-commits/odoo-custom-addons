# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TemplateBackend(models.Model):
    _name = 'nexora.template_backend'
    _description = 'Backend Template Registry'
    _order = 'code asc'

    name = fields.Char(string="Template Name", required=True)
    code = fields.Char(
        string="Technical Key",
        required=True,
        index=True,
        help="Unique identifier used in generation references (e.g. fastapi_service, odoo_module)"
    )
    description = fields.Text(string="Description")
    git_repo_url = fields.Char(
        string="Git Repository URL",
        help="Remote repository URL or local storage URI where template source is maintained."
    )
    subfolder_path = fields.Char(
        string="Subfolder Path",
        default="backend/fastapi-service",
        help="Path inside the template storage tree (e.g. backend/fastapi-service)"
    )
    framework = fields.Selection([
        ('fastapi', 'Python / FastAPI'),
        ('odoo', 'Python / Odoo Addon'),
        ('django', 'Python / Django / DRF'),
        ('nodejs', 'Node.js / Express / Nest'),
        ('spring', 'Java / Spring Boot'),
        ('flask', 'Python / Flask'),
        ('other', 'Other Backend Framework')
    ], string="Framework", default='fastapi', required=True)

    version_ids = fields.One2many(
        'nexora.template_version',
        'backend_template_id',
        string="Versions"
    )
    compatibility_ids = fields.One2many(
        'nexora.template_compatibility',
        'backend_template_id',
        string="Frontend Compatibility"
    )
    metadata_id = fields.Many2one(
        'nexora.template_metadata',
        string="Default Metadata Specification"
    )
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The technical key for backend template must be unique across the Template Store.')
    ]
