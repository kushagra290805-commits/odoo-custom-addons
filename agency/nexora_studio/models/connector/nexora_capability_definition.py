# -*- coding: utf-8 -*-
"""
nexora.capability_definition — Capability Definition
Part 4 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraCapabilityDefinition(models.Model):
    _name = 'nexora.capability_definition'
    _description = 'Capability Definition'
    _order = 'namespace asc'

    namespace = fields.Char(string='Namespace', required=True, index=True)
    display_name = fields.Char(string='Display Name', required=True)
    version = fields.Char(string='Version', default='1.0.0', required=True)
    
    description = fields.Text(string='Description')
    
    input_schema = fields.Text(string='Input Schema (JSON)', default='{}')
    output_schema = fields.Text(string='Output Schema (JSON)', default='{}')
    
    is_read_only = fields.Boolean(string='Read Only', default=True)
    requires_authentication = fields.Boolean(string='Requires Authentication', default=False)
    
    _sql_constraints = [
        ('unique_namespace_version', 'unique(namespace, version)', 'Capability namespace and version must be unique!')
    ]
