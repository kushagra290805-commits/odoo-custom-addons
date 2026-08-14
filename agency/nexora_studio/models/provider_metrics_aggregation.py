from odoo import models, fields, api

class NexoraProviderMetricsAgg(models.Model):
    _name = 'nexora.provider.metrics_aggregation'
    _description = 'Provider Metrics 24h Snapshot'
    _order = 'window_end desc'
    
    provider_id = fields.Char(string='Provider ID', required=True, index=True)
    
    window_start = fields.Datetime(string='Window Start', required=True)
    window_end = fields.Datetime(string='Window End', required=True, index=True)
    
    request_count = fields.Integer(string='Request Count', default=0)
    success_count = fields.Integer(string='Success Count', default=0)
    error_count = fields.Integer(string='Error Count', default=0)
    fallback_count = fields.Integer(string='Fallback Count', default=0)
    retry_count = fields.Integer(string='Retry Count', default=0)
    
    avg_latency_ms = fields.Float(string='Average Latency (ms)', digits=(10, 2))
    p95_latency_ms = fields.Float(string='p95 Latency (ms)', digits=(10, 2))
    
    cache_hit_ratio = fields.Float(string='Cache Hit Ratio', digits=(5, 4))
    total_tokens_consumed = fields.Integer(string='Total Tokens Consumed')
