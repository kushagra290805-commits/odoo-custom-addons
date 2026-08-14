# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TemplateFrontend(models.Model):
    _name = 'nexora.template_frontend'
    _description = 'Frontend Template Registry'
    _order = 'code asc'

    name = fields.Char(string="Template Name", required=True)
    code = fields.Char(
        string="Technical Key",
        required=True,
        index=True,
        help="Unique identifier used in generation references (e.g. vue3_spa, nextjs_app)"
    )
    description = fields.Text(string="Description")
    git_repo_url = fields.Char(
        string="Git Repository URL",
        help="Remote repository URL or local storage URI where template source is maintained."
    )
    subfolder_path = fields.Char(
        string="Subfolder Path",
        default="frontend/vue-spa",
        help="Path inside the template storage tree (e.g. frontend/vue-spa)"
    )
    framework = fields.Selection([
        ('vue', 'Vue.js / Nuxt'),
        ('nextjs', 'Next.js / React'),
        ('react', 'React SPA'),
        ('angular', 'Angular'),
        ('svelte', 'Svelte / SvelteKit'),
        ('vanilla', 'Vanilla HTML/JS/CSS'),
        ('other', 'Other Framework')
    ], string="Framework", default='vue', required=True)

    version_ids = fields.One2many(
        'nexora.template_version',
        'frontend_template_id',
        string="Versions"
    )
    compatibility_ids = fields.One2many(
        'nexora.template_compatibility',
        'frontend_template_id',
        string="Backend Compatibility"
    )
    metadata_id = fields.Many2one(
        'nexora.template_metadata',
        string="Default Metadata Specification"
    )
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The technical key for frontend template must be unique across the Template Store.')
    ]
