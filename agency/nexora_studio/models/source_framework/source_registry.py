# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SourceRegistry(models.Model):
    _name = 'nexora.source_registry'
    _description = 'Component Source Provider Registry'
    _order = 'sequence, name'

    name = fields.Char(required=True, help="Human-readable name of the provider (e.g., GitHub, Penpot)")
    technical_name = fields.Char(required=True, index=True, help="Technical identifier (e.g., github_mcp)")
    adapter_class = fields.Char(required=True, help="Python module/class name of the adapter (e.g., github_adapter.GitHubAdapter)")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    
    # Provider capabilities
    capabilities = fields.Char(help="Comma-separated list of capabilities, e.g., SEARCH,PREVIEW,DOWNLOAD")
    
    # Connector linking (Phase 29)
    connector_id = fields.Many2one('nexora.connector', string="Active Connector", ondelete="set null", help="Link to Phase 28 physical connector")
    is_mcp = fields.Boolean(compute="_compute_is_mcp", store=True, help="True if this is an MCP source")

    # Configuration / Credentials (Legacy)
    config_json = fields.Text(help="DEPRECATED: JSON configuration or credentials. Use nexora.mcp_credential for secrets.")
    
    _sql_constraints = [
        ('technical_name_uniq', 'unique(technical_name)', 'The technical name of the provider must be unique!')
    ]
    
    @api.depends('adapter_class')
    def _compute_is_mcp(self):
        for record in self:
            record.is_mcp = 'McpSourceAdapter' in (record.adapter_class or '')
