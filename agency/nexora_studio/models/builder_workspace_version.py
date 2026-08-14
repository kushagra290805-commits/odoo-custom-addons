# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

class BuilderWorkspaceVersion(models.Model):
    _name = 'nexora.builder.workspace.version'
    _description = 'Builder Workspace Version'
    _order = 'create_date desc, version_number desc'

    name = fields.Char(string='Name', required=True)
    version_uuid = fields.Char(string='Version UUID', default=lambda self: str(uuid.uuid4()), readonly=True, required=True, copy=False)
    version_number = fields.Integer(string='Version Number', required=True, default=1)
    
    session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade')
    parent_version_id = fields.Many2one('nexora.builder.workspace.version', string='Parent Version', ondelete='set null')
    execution_plan_id = fields.Many2one('nexora.builder.execution_plan', string='Execution Plan', ondelete='set null')
    
    change_summary = fields.Text(string='Change Summary')
    approval_status = fields.Selection([
        ('pending', 'Pending Approval'),
        ('partial', 'Partially Approved'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('auto_committed', 'Auto-Committed (System)')
    ], string='Approval Status', default='auto_committed')
    
    snapshot_hash = fields.Char(string='Snapshot Hash', readonly=True)
    author_id = fields.Many2one('res.users', string='Author', default=lambda self: self.env.user)
    
    # JSON Payloads acting as the canonical source of truth
    component_tree_data = fields.Text(string='Component Tree (JSON)', default='{}')
    theme_data = fields.Text(string='Theme Data (JSON)', default='{}')
    assets_data = fields.Text(string='Assets Data (JSON)', default='{}')
    content_data = fields.Text(string='Content Data (JSON)', default='{}')
    layout_data = fields.Text(string='Layout Data (JSON)', default='{}')
    
    @api.model_create_multi
    def create(self, vals_list):
        import hashlib
        for vals in vals_list:
            if not vals.get('snapshot_hash'):
                components = vals.get('component_tree_data', '{}') or '{}'
                theme = vals.get('theme_data', '{}') or '{}'
                assets = vals.get('assets_data', '{}') or '{}'
                content = vals.get('content_data', '{}') or '{}'
                layout = vals.get('layout_data', '{}') or '{}'
                
                hash_source = f"{components}|{theme}|{assets}|{layout}|{content}"
                vals['snapshot_hash'] = hashlib.sha256(hash_source.encode('utf-8')).hexdigest()
        return super().create(vals_list)