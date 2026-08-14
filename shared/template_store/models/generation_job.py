# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class GenerationJob(models.Model):
    _name = 'nexora.generation_job'
    _description = 'Template Generation Job'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Job Reference', required=True, default=lambda self: _('New Generation Job'))
    job_uuid = fields.Char(string='Job UUID', required=True, copy=False, index=True, default=lambda self: str(uuid.uuid4()))
    
    pipeline_id = fields.Many2one('nexora.generation_pipeline', string='Pipeline', required=True)
    generator_type_id = fields.Many2one('nexora.generator_type', string='Generator Type')
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('validating', 'Validating (Legacy)'),
        ('preparing', 'Preparing Workspace (Legacy)'),
        ('cloning', 'Cloning Templates (Legacy)'),
        ('merging', 'Merging Templates (Legacy)'),
        ('replacing', 'Replacing Variables (Legacy)'),
        ('configuring', 'Generating Configuration (Legacy)'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('rolled_back', 'Rolled Back')
    ], string='Status', required=True, default='draft', index=True)
    
    current_stage_id = fields.Many2one('nexora.generation_stage', string='Current Stage')
    completed_stage_ids = fields.Many2many('nexora.generation_stage', string='Completed Stages')
    progress = fields.Float(string='Progress', compute='_compute_progress', store=True)

    @api.depends('completed_stage_ids', 'pipeline_id.stage_ids')
    def _compute_progress(self):
        for record in self:
            total = len(record.pipeline_id.stage_ids.filtered(lambda s: s.active)) if record.pipeline_id else 0
            if total > 0:
                record.progress = (len(record.completed_stage_ids) / total) * 100
            else:
                record.progress = 0.0

    target_workspace_path = fields.Char(string='Target Workspace Path', required=True)
    template_frontend_ref = fields.Char(string='Frontend Template Reference')
    template_backend_ref = fields.Char(string='Backend Template Reference')
    
    frontend_template_id = fields.Many2one('nexora.template_frontend', string='Frontend Template')
    backend_template_id = fields.Many2one('nexora.template_backend', string='Backend Template')
    
    variable_ids = fields.One2many('nexora.generation_variable', 'job_id', string='Substitution Variables')
    log_ids = fields.One2many('nexora.generation_log', 'job_id', string='Execution Logs')
    
    start_time = fields.Datetime(string='Start Time', copy=False)
    end_time = fields.Datetime(string='End Time', copy=False)
    error_message = fields.Text(string='Last Error Message', copy=False)
    metadata_json = fields.Text(string='Metadata JSON', default='{}')

    @api.onchange('pipeline_id')
    def _onchange_pipeline_id(self):
        if self.pipeline_id and self.pipeline_id.generator_type_id:
            self.generator_type_id = self.pipeline_id.generator_type_id

    @api.onchange('frontend_template_id', 'backend_template_id')
    def _onchange_template_ids(self):
        if self.frontend_template_id:
            self.template_frontend_ref = f"template_store://{self.frontend_template_id.subfolder_path}"
        if self.backend_template_id:
            self.template_backend_ref = f"template_store://{self.backend_template_id.subfolder_path}"

    def action_start_generation(self):
        for record in self:
            if record.status not in ('draft', 'failed', 'rolled_back', 'paused', 'cancelled', 'queued'):
                raise UserError(_("Only draft, queued, paused, cancelled, failed, or rolled back jobs can be initiated."))
            record.status = 'queued'
        return True

    def action_rollback(self):
        for record in self:
            if record.status in ('draft', 'rolled_back', 'queued', 'completed'):
                raise UserError(_("Job is not currently in a state that requires rollback."))
            # To be intercepted by orchestrator
        return True

    def action_reset_draft(self):
        for record in self:
            record.write({
                'status': 'draft',
                'error_message': False,
                'start_time': False,
                'end_time': False
            })
        return True
