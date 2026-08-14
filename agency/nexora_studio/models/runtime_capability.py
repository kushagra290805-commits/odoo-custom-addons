# -*- coding: utf-8 -*-
from odoo import models, fields, api

class RuntimeCapability(models.Model):
    _name = 'nexora.runtime_capability'
    _description = 'Runtime Capability Registry'

    name = fields.Char(string='Name', required=True)
    runtime_type = fields.Char(string='Runtime Type', required=True, index=True)
    provider = fields.Char(string='Provider', required=True, default='nexora')
    version = fields.Char(string='Version', required=True, default='1.0.0')
    
    plugin_service = fields.Char(string='Plugin Service', required=True)
    plugin_class = fields.Char(string='Plugin Class')
    
    enabled = fields.Boolean(string='Enabled', default=True)
    optional = fields.Boolean(string='Optional', default=False)
    
    startup_priority = fields.Integer(string='Startup Priority', default=100)
    
    # Dependencies (self-referential M2M)
    dependency_ids = fields.Many2many(
        'nexora.runtime_capability',
        'nexora_runtime_capability_dependency_rel',
        'capability_id',
        'dependency_id',
        string='Dependencies'
    )
    
    supports_health_checks = fields.Boolean(string='Supports Health Checks', default=False)
    
    restart_policy = fields.Selection([
        ('always', 'Always'),
        ('on_failure', 'On Failure'),
        ('never', 'Never')
    ], string='Restart Policy', default='always', required=True)
    
    metadata_json = fields.Text(string='Metadata JSON')
    description = fields.Text(string='Description')
    
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('runtime_type_uniq', 'unique (runtime_type)', 'The Runtime Type must be unique across all capabilities!')
    ]
