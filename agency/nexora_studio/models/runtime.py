# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

class Runtime(models.Model):
    _name = 'nexora.runtime'
    _description = 'Builder Runtime'

    name = fields.Char(string='Name', required=True)
    runtime_uuid = fields.Char(string='Runtime UUID', required=True, default=lambda self: str(uuid.uuid4()), copy=False, readonly=True)
    
    runtime_type = fields.Selection([
        ('workspace', 'Workspace'),
        ('git', 'Git'),
        ('ide', 'IDE'),
        ('preview', 'Preview'),
        ('mcp', 'MCP'),
        ('ai', 'AI'),
        ('deployment', 'Deployment'),
        ('docker', 'Docker'),
        ('custom', 'Custom')
    ], string='Runtime Type', required=True)
    
    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade')
    
    status = fields.Selection([
        ('stopped', 'Stopped'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('busy', 'Busy'),
        ('stopping', 'Stopping'),
        ('error', 'Error')
    ], string='Status', default='stopped', required=True)
    
    health = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical')
    ], string='Health', default='unknown', required=True)
    
    endpoint = fields.Char(string='Endpoint')
    port = fields.Integer(string='Port')
    process_id = fields.Integer(string='Process ID')
    version = fields.Char(string='Version')
    metadata_json = fields.Text(string='Metadata JSON')
    
    started_at = fields.Datetime(string='Started At', readonly=True)
    stopped_at = fields.Datetime(string='Stopped At', readonly=True)
    last_activity = fields.Datetime(string='Last Activity', readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('runtime_uuid_uniq', 'unique (runtime_uuid)', 'The Runtime UUID must be unique!'),
        ('session_type_uniq', 'unique (builder_session_id, runtime_type)', 'A Builder Session can only have one runtime of each type!')
    ]
