from odoo import models, fields, api

class NexoraProviderMigrationLog(models.Model):
    _name = 'nexora.provider.migration_log'
    _description = 'Provider Migration Log'
    _order = 'started_at desc'
    
    provider_id = fields.Char(string='Provider ID', required=True, index=True)
    registry_id = fields.Many2one('nexora.provider.registry', string='Registry Entry')
    
    from_version = fields.Char(string='From Version', required=True)
    to_version = fields.Char(string='To Version', required=True)
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back')
    ], string='Status', required=True, default='pending', index=True)
    
    started_at = fields.Datetime(string='Started At', default=fields.Datetime.now, required=True)
    completed_at = fields.Datetime(string='Completed At')
    error_detail = fields.Text(string='Error Detail')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('provider_id') and not vals.get('registry_id'):
                registry = self.env['nexora.provider.registry'].search([('provider_id', '=', vals['provider_id'])], limit=1)
                if registry:
                    vals['registry_id'] = registry.id
        return super().create(vals_list)
