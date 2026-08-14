from odoo import models, fields, api

class NexoraProviderRuntimeState(models.Model):
    _name = 'nexora.provider.runtime_state'
    _description = 'Provider Runtime State Machine'
    
    provider_id = fields.Char(string='Provider ID', required=True, index=True)
    registry_id = fields.Many2one('nexora.provider.registry', string='Registry Entry', compute='_compute_registry_id', store=True)
    
    current_state = fields.Selection([
        ('installed', 'Installed'),
        ('configured', 'Configured'),
        ('authenticated', 'Authenticated'),
        ('healthy', 'Healthy'),
        ('ready', 'Ready'),
        ('busy', 'Busy'),
        ('degraded', 'Degraded'),
        ('disabled', 'Disabled'),
        ('archived', 'Archived')
    ], string='Current State', required=True, default='installed', index=True)
    
    degradation_reason = fields.Text(string='Degradation Reason')
    
    @api.depends('provider_id')
    def _compute_registry_id(self):
        for record in self:
            if record.provider_id:
                registry = self.env['nexora.provider.registry'].search([('provider_id', '=', record.provider_id)], limit=1)
                record.registry_id = registry.id if registry else False
