# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorEvent(models.Model):
    _name = 'nexora.connector_event'
    _description = 'Nexora Connector Event'
    _order = 'occurred_at desc'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    event_type = fields.Char(string='Event Type', required=True, index=True, help='e.g., lifecycle.transition, health.check, execution.complete')
    severity = fields.Selection([('debug','Debug'),('info','Info'),('warning','Warning'),('error','Error'),('critical','Critical')], string='Severity', default='info', required=True, index=True)
    message = fields.Text(string='Message')
    event_data_json = fields.Text(string='Event Data (JSON)', default='{}')
    occurred_at = fields.Datetime(string='Occurred At', default=fields.Datetime.now, index=True)
    correlation_id = fields.Char(string='Correlation ID', index=True)
