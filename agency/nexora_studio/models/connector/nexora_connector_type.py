# -*- coding: utf-8 -*-
"""
nexora.connector_type — Connector Type Registry (Odoo Model)
Part 7 of Phase 26 — Universal Connector Platform Foundation.
"""
from odoo import models, fields, api


class NexoraConnectorType(models.Model):
    _name = 'nexora.connector_type'
    _description = 'Nexora Connector Type'
    _order = 'name asc'

    type_code = fields.Char(
        string='Type Code', required=True, index=True,
        help='Unique machine-readable type code (e.g., mcp, rest, cli, docker).'
    )
    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    icon = fields.Char(string='Icon', default='gear')
    lifecycle_policy = fields.Selection([
        ('managed', 'Managed'),
        ('ephemeral', 'Ephemeral'),
        ('persistent', 'Persistent'),
        ('manual', 'Manual'),
    ], string='Lifecycle Policy', default='managed', required=True)
    supports_health_check = fields.Boolean(string='Supports Health Check', default=True)
    supports_multiple_instances = fields.Boolean(string='Multiple Instances', default=True)
    requires_session = fields.Boolean(string='Requires Session', default=False)
    is_remotely_installable = fields.Boolean(string='Remote Installable', default=False)
    supports_hot_reload = fields.Boolean(string='Hot Reload', default=False)
    required_credential_types = fields.Char(
        string='Required Credential Types',
        help='Comma-separated list of required credential types.'
    )
    is_builtin = fields.Boolean(string='Built-in', default=False, readonly=True)
    active = fields.Boolean(string='Active', default=True)
    connector_count = fields.Integer(
        string='Connector Count', compute='_compute_connector_count', store=False
    )

    _sql_constraints = [
        ('unique_type_code', 'unique(type_code)', 'Connector type code must be unique!'),
    ]

    @api.depends()
    def _compute_connector_count(self):
        for record in self:
            record.connector_count = self.env['nexora.connector'].search_count(
                [('connector_type_id', '=', record.id)]
            )
