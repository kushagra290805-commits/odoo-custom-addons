# -*- coding: utf-8 -*-
"""
nexora.connector_health — Connector Structured Telemetry
Part 6 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraConnectorHealth(models.Model):
    _name = 'nexora.connector_health'
    _description = 'Nexora Connector Health Record'
    _order = 'last_checked desc'

    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    status = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('failed', 'Failed')
    ], string='Status', default='unknown', required=True, index=True)
    
    availability = fields.Float(string='Availability', default=1.0, help='Uptime ratio from 0.0 to 1.0')
    latency_ms = fields.Float(string='Latency (ms)', default=0.0)
    
    auth_status = fields.Char(string='Authentication Status', default='unknown')
    quota_status = fields.Selection([
        ('ok', 'OK'),
        ('near_limit', 'Near Limit'),
        ('exhausted', 'Exhausted')
    ], string='Quota Status', default='ok')
    rate_limit_status = fields.Selection([
        ('ok', 'OK'),
        ('near_limit', 'Near Limit'),
        ('exhausted', 'Exhausted')
    ], string='Rate Limit Status', default='ok')
    
    version_drift = fields.Boolean(string='Version Drift', default=False)
    config_drift = fields.Boolean(string='Configuration Drift', default=False)
    
    heartbeat_timestamp = fields.Datetime(string='Last Heartbeat')
    last_successful_execution = fields.Datetime(string='Last Successful Execution')
    last_checked = fields.Datetime(string='Last Checked', default=fields.Datetime.now)
    
    error_detail = fields.Text(string='Error Detail')
    consecutive_failures = fields.Integer(string='Consecutive Failures', default=0)
    consecutive_successes = fields.Integer(string='Consecutive Successes', default=0)
    telemetry_metadata_json = fields.Text(string='Telemetry Metadata (JSON)', default='{}')
