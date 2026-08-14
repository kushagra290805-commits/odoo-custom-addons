# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorDiagnostic(models.Model):
    _name = 'nexora.connector_diagnostic'
    _description = 'Nexora Connector Diagnostic'
    _order = 'run_at desc'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    diagnostic_type = fields.Char(string='Diagnostic Type', required=True, help='e.g., ping, auth, capability_smoke_test')
    passed = fields.Boolean(string='Passed', default=False, index=True)
    result_json = fields.Text(string='Result (JSON)', default='{}')
    error = fields.Text(string='Error')
    run_at = fields.Datetime(string='Run At', default=fields.Datetime.now, index=True)
    duration_ms = fields.Float(string='Duration (ms)', default=0.0)
