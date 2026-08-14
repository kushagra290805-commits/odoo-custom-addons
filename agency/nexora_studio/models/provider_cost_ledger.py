from odoo import models, fields, api

class NexoraProviderCostLedger(models.Model):
    _name = 'nexora.provider.cost_ledger'
    _description = 'Provider Cost Ledger'
    _order = 'timestamp desc'
    
    session_uuid = fields.Char(string='Session UUID', required=True, index=True)
    provider_id = fields.Char(string='Provider ID', required=True, index=True)
    
    usd_cost = fields.Float(string='USD Cost', required=True, digits=(10, 6))
    units_consumed = fields.Float(string='Units Consumed', required=True, digits=(10, 2))
    unit_type = fields.Char(string='Unit Type', required=True) # e.g. 'tokens', 'gb', 'seconds'
    
    timestamp = fields.Datetime(string='Timestamp', required=True, default=fields.Datetime.now, index=True)
