# -*- coding: utf-8 -*-
from odoo import models, fields

class GenerationStage(models.Model):
    _name = 'nexora.generation_stage'
    _description = 'Template Generation Pipeline Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True)
    code = fields.Char(string='Stage Code', required=True)
    pipeline_id = fields.Many2one('nexora.generation_pipeline', string='Pipeline', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    stage_type = fields.Selection([
        ('validation', 'Validate Templates'),
        ('preparation', 'Prepare Workspace'),
        ('cloning', 'Clone Template'),
        ('merge', 'Merge Frontend + Backend'),
        ('variable', 'Replace Variables'),
        ('config', 'Generate Configuration'),
        ('finalize', 'Finalize Workspace')
    ], string='Stage Type', required=True, default='validation')

    service_name = fields.Char(string='Service Model Name', required=True, default='nexora.generation_service',
                               help="The abstract Odoo service model responsible for executing this stage.")
    
    can_rollback = fields.Boolean(string='Supports Rollback', default=True)
    description = fields.Text(string='Description')
    metadata_json = fields.Text(string='Metadata JSON', default='{}')
    active = fields.Boolean(string='Active', default=True)
