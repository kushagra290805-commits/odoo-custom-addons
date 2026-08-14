from odoo import models, fields, api

class NexoraProviderCacheBlob(models.Model):
    _name = 'nexora.provider.cache_blob'
    _description = 'Provider Execution Cache (L3)'
    _rec_name = 'cache_key'
    
    cache_key = fields.Char(string='Cache Key', required=True, index=True, unique=True)
    cache_value_json = fields.Text(string='Cached Value (JSON)', required=True)
    
    expires_at = fields.Datetime(string='Expires At', index=True)
    is_stale = fields.Boolean(string='Is Stale', default=False, index=True)
