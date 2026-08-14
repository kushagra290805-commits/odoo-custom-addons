# -*- coding: utf-8 -*-
from odoo import models, fields

class NexoraAIAuditLog(models.Model):
    _name = 'nexora.ai_audit_log'
    _description = 'AI Generation Audit Log'
    _order = 'create_date desc'

    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade')
    generation_stage = fields.Char(string='Generation Stage', required=True)
    
    # Provider & Model tracking
    ai_provider = fields.Char(string='AI Provider', required=True)
    ai_model_name = fields.Char(string='Model Name', required=True)
    
    # Prompt & Execution tracking
    prompt_template_id = fields.Char(string='Prompt Template Identifier')
    prompt_content = fields.Text(string='Prompt Sent')
    response_content = fields.Text(string='Response Received')
    generation_parameters = fields.Text(string='Generation Parameters (JSON)')
    execution_duration = fields.Float(string='Execution Duration (Seconds)')
    token_usage = fields.Integer(string='Token Usage')
    failure_reason = fields.Text(string='Failure Reason')
    
    # Patch tracking
    affected_files = fields.Text(string='Affected Files (Comma Separated)')
    patch_diff = fields.Text(string='Produced Diff / Patch')
    git_commit_hash = fields.Char(string='Git Commit Hash')
    
    # Audit tracking
    developer_id = fields.Many2one('res.users', string='Approving Developer')
    approval_timestamp = fields.Datetime(string='Approval Timestamp')
    
    status = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('modified', 'Modified by Developer'),
        ('failed', 'Execution Failed')
    ], string='Status', default='pending', required=True)
