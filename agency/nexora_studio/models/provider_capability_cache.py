from odoo import models, fields, api

class NexoraProviderCapabilityCache(models.Model):
    _name = 'nexora.provider.capability_cache'
    _description = 'Provider Capability Manifest Cache'
    _rec_name = 'provider_id'
    
    provider_id = fields.Char(string='Provider ID', required=True, index=True, unique=True)
    capabilities_json = fields.Text(string='Capabilities Manifest (JSON)', required=True)
    
    cached_at = fields.Datetime(string='Cached At', default=fields.Datetime.now)
    expires_at = fields.Datetime(string='Expires At', index=True)
    is_stale = fields.Boolean(string='Is Stale', default=False, index=True)
