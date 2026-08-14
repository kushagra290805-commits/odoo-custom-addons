# -*- coding: utf-8 -*-
from odoo import models, fields


class AICatalogSyncLog(models.Model):
    _name = 'nexora.ai_catalog_sync_log'
    _description = 'AI Catalog Sync Log'
    _order = 'sync_date desc'

    provider = fields.Selection([
        ('openrouter', 'OpenRouter'),
        ('ollama', 'Ollama'),
        ('nvidia', 'NVIDIA Build'),
        ('openai', 'OpenAI'),
        ('claude', 'Claude'),
        ('anthropic', 'Anthropic'),
        ('gemini', 'Gemini'),
        ('generic_openai', 'Generic OpenAI'),
        ('airouter', 'AIRouter.in'),
        ('groq', 'Groq'),
        ('test', 'Test Provider')
    ], string='Provider', required=True, index=True)
    
    sync_date = fields.Datetime('Sync Date', default=fields.Datetime.now, required=True, index=True)
    catalog_revision = fields.Integer('Revision', default=1, required=True)
    provider_catalog_hash = fields.Char('Catalog Hash')
    
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error')
    ], string='Status', required=True, default='success')
    
    error_message = fields.Text('Error Message')
    
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    duration_seconds = fields.Float('Duration (s)')
    
    models_fetched = fields.Integer('Models Fetched', default=0)
    models_added = fields.Integer('Models Added', default=0)
    models_updated = fields.Integer('Models Updated', default=0)
    models_deprecated = fields.Integer('Models Deprecated', default=0)
    models_removed = fields.Integer('Models Removed', default=0)
    
    summary_json = fields.Text('Sync Summary (JSON)', help="Details about models added, removed, or changed.")
    
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"Sync {rec.provider} (Rev {rec.catalog_revision}) - {rec.sync_date}"))
        return result
