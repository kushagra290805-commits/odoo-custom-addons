# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid

class BuilderConfiguration(models.Model):
    _name = 'nexora.builder_configuration'
    _description = 'Builder Configuration'
    
    # FUTURE RELATIONSHIPS:
    # Future versions will relate Builder Configurations to:
    # - Template
    # - Deployment
    # - Workspace
    # - Preview Server
    # - Git Repository
    # - AI Context

    name = fields.Char(string='Name', required=True)
    configuration_uuid = fields.Char(string='Configuration UUID', required=True, default=lambda self: str(uuid.uuid4()), copy=False, readonly=True)
    semantic_version = fields.Char(string='Version', default='1.0.0', required=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('locked', 'Locked'),
        ('archived', 'Archived')
    ], string='Status', default='draft', required=True, copy=False)
    
    environment = fields.Selection([
        ('development', 'Development'),
        ('testing', 'Testing'),
        ('production', 'Production')
    ], string='Environment', default='development', required=True)
    
    description = fields.Text(string='Description')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)
    
    git_history_sync_limit = fields.Integer(string='Git History Sync Limit', default=50, required=True,
                                            help="Maximum number of commits to synchronize into the database per Git Runtime.")


    def unlink(self):
        # Prevent deletion if referenced by Builder Sessions
        sessions = self.env['nexora.builder_session'].search([('builder_configuration_id', 'in', self.ids)], limit=1)
        if sessions:
            raise ValidationError(_('Cannot delete a Builder Configuration that is referenced by one or more Builder Sessions.'))
        return super(BuilderConfiguration, self).unlink()

    def action_lock_configuration(self):
        service = self.env['nexora.builder_configuration_service']
        for record in self:
            service.lock_configuration(record.id)

    def action_archive_configuration(self):
        service = self.env['nexora.builder_configuration_service']
        for record in self:
            service.archive_configuration(record.id)

    def action_clone_configuration(self):
        service = self.env['nexora.builder_configuration_service']
        new_configs = self.env['nexora.builder_configuration']
        for record in self:
            new_configs |= service.clone_configuration(record.id)
        
        # Return an action to open the newly cloned configurations
        if len(new_configs) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cloned Builder Configuration'),
                'res_model': 'nexora.builder_configuration',
                'view_mode': 'form',
                'res_id': new_configs.id,
                'target': 'current',
            }
        elif len(new_configs) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cloned Builder Configurations'),
                'res_model': 'nexora.builder_configuration',
                'view_mode': 'list,form',
                'domain': [('id', 'in', new_configs.ids)],
                'target': 'current',
            }

    def write(self, vals):
        # Allow system/scripts to change status, but developers cannot change technical fields after creation
        # Since this is an internal model, we'll enforce immutability for most fields.
        restricted_fields = ['name', 'environment', 'git_history_sync_limit']
        for record in self:
            if record.status in ['locked', 'archived'] and any(f in vals for f in restricted_fields):
                raise ValidationError(_('Builder Configuration is immutable after creation. Technical specifications cannot be modified.'))
        return super(BuilderConfiguration, self).write(vals)
