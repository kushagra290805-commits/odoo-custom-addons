# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorCapability(models.Model):
    _name = 'nexora.connector_capability'
    _description = 'Nexora Connector Capability'
    _order = 'priority desc'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    capability_definition_id = fields.Many2one('nexora.capability_definition', string='Definition', required=True, ondelete='restrict', index=True)
    priority = fields.Integer(string='Priority', default=10)
    estimated_latency_ms = fields.Integer(string='Est. Latency (ms)', default=1000)
    estimated_cost_usd = fields.Float(string='Est. Cost (USD)', default=0.0)
    enabled = fields.Boolean(string='Enabled', default=True)
    _sql_constraints = [('unique_connector_definition', 'unique(connector_id, capability_definition_id)', 'A connector can only implement a capability definition once!')]
