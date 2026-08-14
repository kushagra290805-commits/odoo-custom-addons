# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

class BuilderExecutionPlan(models.Model):
    _name = 'nexora.builder.execution_plan'
    _description = 'Builder Execution Plan'

    name = fields.Char(string='Plan Name', required=True)
    plan_uuid = fields.Char(string='Plan UUID', default=lambda self: str(uuid.uuid4()), readonly=True, required=True, copy=False)
    session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade')
    
    # Immutable plan payload
    plan_payload = fields.Text(string='Execution Plan Payload (JSON)', required=True, readonly=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('validating', 'Validating'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('rolled_back', 'Rolled Back'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', required=True)
    
    # Execution result is stored separately from the immutable plan payload
    execution_result = fields.Text(string='Execution Result (JSON)')
    rollback_reason = fields.Text(string='Rollback Reason')
    
    impact_estimate = fields.Text(string='Impact Estimate (JSON)')
    cost_estimate = fields.Float(string='Cost Estimate')
    
    def action_approve(self):
        self.write({'status': 'approved'})
        
    def action_reject(self):
        self.write({'status': 'rejected'})
