# -*- coding: utf-8 -*-
"""
AI Execution History

Odoo model for tracking the telemetry of all AI executions across the pipeline.
"""
from odoo import models, fields


class AIExecutionHistory(models.Model):
    _name = 'nexora.ai_execution_history'
    _description = 'AI Execution History & Telemetry'
    _order = 'create_date desc'

    execution_id = fields.Char(string='Execution ID', required=True, index=True)
    request_id = fields.Char(string='Request ID', index=True)
    job_id = fields.Integer(string='Job ID', index=True)
    
    # Traceability
    workspace_id = fields.Many2one('nexora.workspace', string='Workspace', index=True)
    project_id = fields.Many2one('nexora.project', string='Project', index=True)
    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', index=True)
    
    provider = fields.Char(string='Provider', index=True)
    model = fields.Char(string='Model', index=True)
    
    latency = fields.Float(string='Latency (s)')
    retry_count = fields.Integer(string='Retry Count', default=0)
    
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Status', required=True, default='success', index=True)
    
    failure_classification = fields.Char(string='Failure Classification')
    error_message = fields.Text(string='Error Message')
    
    cost = fields.Float(string='Estimated Cost (USD)', digits=(12, 6))
    
    # Token Accounting
    token_usage = fields.Integer(string='Total Token Usage')  # Kept for backward compatibility
    prompt_tokens = fields.Integer(string='Prompt Tokens', default=0)
    completion_tokens = fields.Integer(string='Completion Tokens', default=0)
    
    # Future-Proofing for Pipeline
    execution_type = fields.Selection([
        ('chat', 'Chat'), 
        ('completion', 'Completion'), 
        ('embedding', 'Embedding'), 
        ('image', 'Image'), 
        ('tool', 'Tool Calling')
    ], string='Execution Type', default='chat')
    is_streaming = fields.Boolean(string='Streaming Request', default=False)
    cache_hit = fields.Boolean(string='Cache Hit', default=False)
    
    resolution_trace = fields.Text(string='Resolution Trace JSON')
    
    started_at = fields.Datetime(string='Started At')
    finished_at = fields.Datetime(string='Finished At')

